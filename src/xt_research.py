"""Reproducible offline training and static research report (no API integration)."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from src.expected_threat import XTConfig, extract_actions, fit, rate_actions, save_model


def train(root, competition, season, limit=12, held_out=2, config=XTConfig(),
          direction='right', source_revision=None):
    """Fit only the first chronological training partition of a local manifest.

    Available status and both regulation Half Ends are integrity checks, not a
    claim of complete season coverage. Bad selected files fail, never resample.
    The final selected matches are held out and used ONLY for scoring/coverage.
    """
    if any(type(value) is not int or value <= 0 for value in (competition, season, limit, held_out)):
        raise ValueError('IDs, limit and held-out count must be positive integers')
    if direction not in ('left', 'right'):
        raise ValueError('Explicit right or left attacking direction required')
    root = Path(root)
    manifest = root / 'matches' / str(competition) / f'{season}.json'
    matches = json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(matches, list) or len({m['match_id'] for m in matches}) != len(matches):
        raise ValueError('Expected a match manifest with unique IDs')
    matches = sorted(matches, key=lambda m: (m['match_date'], m['match_id']))
    eligible = [m for m in matches if m.get('match_status') == 'available' and
                (root / 'events' / f"{m['match_id']}.json").exists()]
    selected = eligible[:limit]
    if held_out < 1 or len(selected)-held_out < 2:
        raise ValueError('Need at least two training matches and one held-out match')
    split = len(selected)-held_out
    frames, counts, hashes = [], [], {}
    for m in selected:
        path = root / 'events' / f"{m['match_id']}.json"
        raw = path.read_bytes()
        hashes[str(m['match_id'])] = hashlib.sha256(raw).hexdigest()
        events = pd.json_normalize(json.loads(raw), sep='_')
        # Raw StatsBomb objects become the established flattened source schema.
        for col in ('type', 'team', 'player', 'pass_outcome', 'shot_outcome'):
            if col+'_name' in events:
                events[col] = events[col+'_name']
        if events.empty or not {'type', 'period', 'location'}.issubset(events):
            raise ValueError(f"Empty/incomplete event file: {m['match_id']}")
        completed_periods = set(events.loc[events.type.eq('Half End'), 'period'])
        if not {1, 2}.issubset(completed_periods):
            raise ValueError(f"Missing regulation Half End markers: {m['match_id']}")
        events['match_id'] = m['match_id']
        actions = extract_actions(events, config, direction)
        frames.append(events)
        counts.append({'match_id': m['match_id'], 'date': m['match_date'],
                       'events': len(events), 'actions': len(actions),
                       'eligible_actions': int(actions.eligible.sum()),
                       'teams': sorted(events.get('team', pd.Series(dtype=str)).dropna().unique().tolist()),
                       'half_end_periods': sorted(completed_periods)})
    metadata = dict(provider='StatsBomb Open Data', competition_id=competition, season_id=season,
                    provenance='https://github.com/statsbomb/open-data', source_revision=source_revision,
                    manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(), event_sha256=hashes,
                    published_matches=len(matches), locally_eligible_matches=len(eligible), selected_matches=counts,
                    train_ids=[m['match_id'] for m in selected[:split]],
                    held_out_ids=[m['match_id'] for m in selected[split:]],
                    missing_available_files=sum(m.get('match_status') == 'available' and
                        not (root / 'events' / f"{m['match_id']}.json").exists() for m in matches),
                    selection='date then match_id ascending, first limit available local files; last held_out reserved',
                    direction=f'explicit input {direction}; normalized attacking right; no home/away or halftime flips',
                    direction_verification='StatsBomb provider contract plus finite pitch bounds; not inferred from event outcomes',
                    assumptions={'failed_moves': 'zero continuation', 'shots': 'terminal',
                        'carry': 'observed successful movement; no failed-carry events',
                        'periods': 'all recorded regulation/extra-time, exclude shootout period 5'})
    model = fit(extract_actions(pd.concat(frames[:split], ignore_index=True), config, direction), config, metadata)
    held = pd.concat(frames[split:], ignore_index=True)
    rated = rate_actions(held, model, direction)
    model['diagnostics']['held_out'] = dict(events=len(held), actions=len(extract_actions(held, config, direction)),
        rated=int(rated.xT.notna().sum()), description='Coverage only; no possession-goal calibration claim')
    return model, rated


def report(model, rated, directory):
    """Write a heatmap, convergence plot and held-out pass table, headlessly."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    heat = axes[0].imshow(model['surface'], extent=[0,120,80,0], aspect='auto')
    axes[0].set(title='Empirical xT (attack right)', xlabel='StatsBomb x', ylabel='StatsBomb y')
    fig.colorbar(heat, ax=axes[0])
    axes[1].semilogy([max(value, 1e-16) for value in model['diagnostics']['residuals']])
    axes[1].set(title='Bellman convergence', xlabel='Iteration', ylabel='Max absolute change')
    fig.tight_layout()
    fig.savefig(directory / 'xt_research.png', dpi=140)
    plt.close(fig)
    columns = ['match_id', 'id', 'player', 'location', 'pass_end_location', 'xT']
    rated.loc[rated.type.eq('Pass') & rated.xT.notna()].reindex(columns=columns).head(30).to_csv(directory / 'selected_passes.csv', index=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('data', help='StatsBomb open-data data/ directory, raw JSON')
    p.add_argument('--competition', type=int, default=9)
    p.add_argument('--season', type=int, default=281)
    p.add_argument('--limit', type=int, default=12)
    p.add_argument('--held-out', type=int, default=2)
    p.add_argument('--nx', type=int, default=16)
    p.add_argument('--ny', type=int, default=12)
    p.add_argument('--direction', choices=['left', 'right'], default='right', help='Input convention: StatsBomb is right; never infer from team/period')
    p.add_argument('--source-revision', help='Optional pinned open-data checkout commit')
    p.add_argument('--output', default='artifacts/xt-v1.json')
    p.add_argument('--report', default='research/xt')
    args = p.parse_args()
    model, rated = train(args.data, args.competition, args.season, args.limit, args.held_out,
                         XTConfig(args.nx, args.ny), args.direction, args.source_revision)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    save_model(model, args.output)
    report(model, rated, args.report)
    print(json.dumps({'training': model['metadata']['train_ids'], 'held_out': model['diagnostics']['held_out'],
                      'iterations': model['diagnostics']['iterations'], 'unobserved_zones': model['diagnostics']['unobserved_zones']}, indent=2))


if __name__ == '__main__':
    main()
