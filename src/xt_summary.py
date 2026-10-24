"""Presentation-ready xT move records and player totals, independent of HTTP/UI."""

import pandas as pd

from src.expected_threat import XTConfig, extract_actions, rate_actions, zone


def valued_moves(events: pd.DataFrame, model: dict) -> pd.DataFrame:
    """Return pass/carry attempts with Python-rated xT and safe endpoint columns.

    Input is flattened StatsBomb attacking-right data and a validated saved model.
    Failed moves, shootouts and malformed locations remain rows with null xT;
    shots are omitted. Coordinates are never inferred from neighboring events.
    Negative and zero values from rate_actions are preserved. Input is not mutated.
    """
    moves = events.loc[events['type'].isin(['Pass', 'Carry'])].copy()
    rated = rate_actions(moves, model, direction='right')
    config = XTConfig(**model['config'])
    # Extraction owns outcome semantics; this adapter only aligns its records.
    extracted = extract_actions(moves, config, direction='right')
    successful = {row.position: bool(row.success) for row in extracted.itertuples()}
    rated['successful'] = [successful.get(i, False) for i in range(len(moves))]
    starts, ends = [], []
    for event in moves.to_dict(orient='records'):
        start = event.get('location')
        end = event.get('pass_end_location' if event['type'] == 'Pass' else 'carry_end_location')
        starts.append(start if zone(start, config) is not None else [None, None])
        ends.append(end if zone(end, config) is not None else [None, None])
    rated['x'] = [p[0] for p in starts]
    rated['y'] = [p[1] for p in starts]
    rated['end_x'] = [p[0] for p in ends]
    rated['end_y'] = [p[1] for p in ends]
    return rated


def player_xt_summary(moves: pd.DataFrame) -> pd.DataFrame:
    """Aggregate valued_moves output by stable player ID, retaining missing totals.

    Positive xT sums positive *rated* deltas; net xT also includes negative deltas.
    Example: +0.03, -0.01, 0, null gives positive=0.03, net=0.02, rated=3.
    A player without rated moves has null totals, not a fabricated zero. Rated
    pass/carry counts describe successful moves with usable endpoints, not minutes
    or attempted dribbles. Unidentified players are excluded from rankings.
    """
    columns = ['player_id', 'player', 'action_count', 'rated_action_count',
               'rated_passes', 'rated_carries', 'positive_xt', 'net_xt']
    rows = []
    for player_id, group in moves.dropna(subset=['player_id']).groupby('player_id', sort=True):
        values = group['xT'].dropna()
        names = group['player'].dropna()
        rows.append(dict(player_id=int(player_id), player=names.iloc[0] if len(names) else str(int(player_id)),
            action_count=len(group), rated_action_count=len(values),
            rated_passes=int((group.type.eq('Pass') & group.xT.notna()).sum()),
            rated_carries=int((group.type.eq('Carry') & group.xT.notna()).sum()),
            # Do not let an empty sum turn "unknown" into "no contribution".
            positive_xt=float(values[values > 0].sum()) if len(values) else None,
            net_xt=float(values.sum()) if len(values) else None))
    return pd.DataFrame(rows, columns=columns)
