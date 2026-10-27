"""ID-based player contributions and transparent, bounded collection aggregates."""
from math import isfinite
from numbers import Real

import pandas as pd

from src.player_comparison import comparison_evidence
from src.metrics import descriptive_statistics, select_shots
from src.playing_time import playing_time, MINUTES_PROVENANCE
from src.progressive import progressive_passes
from src.xt_summary import valued_moves, player_xt_summary

DEFINITIONS = {
    "sample": "Explicit selected match collection, not a full league season. Failed matches are excluded and listed. No percentile reference population.",
    "identity": "Provider player ID within explicit competition/season/team context; names are labels and aliases, never grouping keys.",
    "appearances": "Count of confirmed appeared=True records; unknown appearances reported separately. Squad inclusion alone is not an appearance.",
    "minutes": MINUTES_PROVENANCE,
    "per90": "90 * metric / elapsed pitch minutes, only with complete valid positive minutes for the numerator's matches. Aggregate rates are null if any included player-match minutes are unknown. No average of per-match rates.",
    "passes": "All recorded pass attempts, excluding shootouts; completed means omitted StatsBomb outcome. Missing geometry stays in the attempts denominator.",
    "completed_progressive_passes": "Completed passes reducing distance to (120,40) by >=10m-equivalent, assuming 105x68m; valid geometry coverage is explicit. Shared Python progression definition.",
    "shots": "Recorded Shot events excluding shootouts; goals are Shot outcome Goal, excluding own-goal events. Not necessarily the provider final score.",
    "xg": "Sum of valid available provider shot probabilities only. shots_with_xg / shots is coverage; all unavailable stays null, including no shots. xG per90 is null for partial shot coverage.",
    "successful_dribbles": "Recorded Dribble outcome Complete; denominator for per90 is valid elapsed pitch minutes, not dribble attempts.",
    "successful_interceptions": "Recorded Interception outcomes Won, Success, Success In Play or Success Out.",
    "xt": "Experimental frozen destination-minus-origin zone values for eligible successful passes/carries. Positive sums positive rated changes; net includes negatives. Rated / attempted actions describes coverage. Null is unrated, not zero; never a player rating. No fitting during requests.",
    "positions": "Provider lineup position history, including tactical changes. No inferred primary position or physical attributes; histories do not themselves certify minutes.",
}
COUNT_METRICS = ("passes", "completed_passes", "completed_progressive_passes", "progressive_valid_geometry", "shots", "goals", "shots_with_xg", "successful_dribbles", "successful_interceptions", "xt_rated_actions", "xt_attempted_actions")
NULLABLE_METRICS = ("xg", "xt_positive", "xt_net")
RATE_METRICS = ("passes", "completed_passes", "completed_progressive_passes", "shots", "goals", "xg", "successful_dribbles", "successful_interceptions", "xt_positive", "xt_net")


def per90(statistics: dict, minutes: float | None) -> dict:
    """Normalize matched numerators/exposure, preserving unknowns and genuine zero.

    Two shots in 30 elapsed minutes gives 90*2/30=6 shots/90. Zero, negative,
    missing and nonfinite minutes give null rates, not infinity. A partial xG
    numerator cannot masquerade as a complete scoring-chance rate.
    """
    valid = isinstance(minutes, Real) and not isinstance(minutes, bool) and isfinite(minutes) and minutes > 0
    return {metric: 90 * statistics[metric] / minutes if valid and statistics.get(metric) is not None and (metric != "xg" or statistics["shots_with_xg"] == statistics["shots"]) else None for metric in RATE_METRICS}


def nullable_sum(values) -> float | None:
    """Sum covered measurements; return null for no finite observations."""
    known = [float(value) for value in values if isinstance(value, Real) and not isinstance(value, bool) and isfinite(value)]
    return sum(known) if known else None


def match_players(events: pd.DataFrame, lineups: pd.DataFrame, match: dict, team_id: int,
                  model: dict | None, model_id: str | None) -> dict[int, dict]:
    """Build one match's ID-keyed profiles using the shared analytics engine.

    Complete event counts include no-touch squad players as zero, but roster
    absence does not invent participation. Shootouts are excluded to align
    contribution numerators with the playing-time denominator. All team move
    values are computed once with an already-fitted model, then grouped by ID.
    Duplicate display names remain distinct people; alternate labels are retained.
    """
    for frame in (events, lineups):
        if "player_id" in frame:
            for value in frame.player_id.dropna():
                if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value) or value <= 0 or value != int(value):
                    raise ValueError("Provider player IDs must be positive integers")
    team_events = events.loc[events.team_id.eq(team_id)].copy()
    if "player_id" not in team_events:
        team_events["player_id"] = None
    if "player" not in team_events:
        team_events["player"] = None
    roster = lineups.loc[lineups.team_id.eq(team_id)] if "team_id" in lineups else pd.DataFrame()
    team_name = str(team_events.team.iloc[0]) if len(team_events) else str(roster.team.iloc[0])
    timing = playing_time(events, lineups, team_id)
    # Period 5 is a shootout, not playing-time exposure. Unknown period data
    # cannot certify minutes; ordinary observed counts remain inspectable.
    measured = team_events.loc[~team_events.get("period", pd.Series(index=team_events.index, dtype=float)).eq(5)]
    progression = progressive_passes(measured, team_name)
    rated = player_xt_summary(valued_moves(measured, model)) if model is not None else pd.DataFrame()
    xt_rows = {int(row['player_id']): row for row in rated.to_dict('records')}
    results = {}
    for player_id, minutes in timing.items():
        own = measured.loc[measured.player_id.eq(player_id)]
        identity = roster.loc[roster.player_id.eq(player_id)] if "player_id" in roster else pd.DataFrame()
        names = set(str(name) for name in own.get("player", pd.Series(dtype=object)).dropna())
        if "substitution_replacement_id" in team_events and "substitution_replacement" in team_events:
            names.update(str(name) for name in team_events.loc[team_events.substitution_replacement_id.eq(player_id), "substitution_replacement"].dropna())
        for tactics in team_events.get("tactics", pd.Series(dtype=object)):
            if isinstance(tactics, dict):
                names.update(str(item["player"]["name"]) for item in tactics.get("lineup", [])
                    if item.get("player", {}).get("id") == player_id and item["player"].get("name"))
        if len(identity):
            names.update(str(name) for name in identity.player.dropna())
        name = str(identity.player.dropna().iloc[0]) if len(identity) and identity.player.notna().any() else sorted(names)[0] if names else f"Player {player_id}"
        observed = descriptive_statistics(own, team_name)
        passes = progression.loc[progression.player_id.eq(player_id)]
        shots = select_shots(own, team_name)
        xt = xt_rows.get(player_id, {})
        statistics = {"passes": observed['Passes'], "completed_passes": observed['Completed passes'],
            "completed_progressive_passes": int(passes.completed_progressive.sum()),
            "progressive_valid_geometry": int(passes.valid_geometry.sum()), "shots": observed['Shots'], "goals": observed['Goals'],
            "xg": nullable_sum([observed['xG']]), "shots_with_xg": int(shots.xg.notna().sum()),
            "successful_dribbles": observed['Successful dribbles'], "successful_interceptions": observed['Successful interceptions'],
            "xt_positive": nullable_sum([xt.get('positive_xt')]), "xt_net": nullable_sum([xt.get('net_xt')]),
            "xt_rated_actions": int(xt.get('rated_action_count', 0)),
            "xt_attempted_actions": int(own.type.isin(['Pass', 'Carry']).sum())}
        history = identity.positions.iloc[0] if len(identity) and "positions" in identity else []
        history = history if isinstance(history, list) else []
        results[player_id] = {"player_id": player_id, "player": name, "aliases": sorted(names),
            "team_id": team_id, "team": team_name,
            "positions": sorted({str(p['position']) for p in history if p.get('position')}), "position_history": history,
            "match_id": int(match['match_id']), "match_date": str(match['match_date']),
            "home_team": match['home_team'], "away_team": match['away_team'],
            **minutes, "minutes_provenance": MINUTES_PROVENANCE, "statistics": statistics,
            "per90": per90(statistics, minutes['minutes']), "model_id": model_id}
    return results


def aggregate_player(contributions: list[dict], *, incomplete_collection: bool = False) -> dict:
    """Pool counts and exposure, never average individual per90 rates.

    A 30-minute 2-shot appearance plus 90-minute 1-shot appearance gives
    90*(2+1)/(30+90)=2.25 shots/90, not mean(6,1)=3.5. Unknown minutes make
    pooled rates null while known_minutes remains an explicitly partial sum.
    Failed selected matches also suppress aggregate rates: their numerators are
    unavailable. xG and xT covered totals remain partial, with coverage counters.
    """
    statistics = {metric: sum(row['statistics'][metric] for row in contributions) for metric in COUNT_METRICS}
    statistics.update({metric: nullable_sum(row['statistics'][metric] for row in contributions) for metric in NULLABLE_METRICS})
    covered = [row for row in contributions if isinstance(row['minutes'], Real) and not isinstance(row['minutes'], bool) and isfinite(row['minutes']) and row['minutes'] >= 0]
    known = nullable_sum(row['minutes'] for row in covered)
    complete = len(covered) == len(contributions) and not incomplete_collection
    minutes = known if complete else None
    result = {"appearances": sum(row['appeared'] is True for row in contributions),
        "unknown_appearances": sum(row['appeared'] is None for row in contributions),
        "minutes": minutes, "known_minutes": known, "minutes_covered_matches": len(covered),
        "statistics": statistics, "per90": per90(statistics, minutes),
        "per90_match_ids": [row['match_id'] for row in contributions] if minutes is not None and minutes > 0 else []}
    result['comparison_evidence'] = comparison_evidence(result, DEFINITIONS, incomplete_collection=incomplete_collection)
    return result
