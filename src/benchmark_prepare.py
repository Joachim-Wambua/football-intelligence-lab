"""Deterministic offline build from raw StatsBomb JSON; never imported by routes.

python -m src.benchmark_prepare DATA_ROOT --competition 72 --season 107 --output OUTPUT
Network collection is a separate explicit command in tools/collect_benchmarks.py.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import gzip
import json
from importlib.metadata import version
from pathlib import Path

import pandas as pd
from statsbombpy.helpers import flatten_event

from src.benchmarks import BENCHMARK_METRICS, POSITION_GROUPS, finite_number, position_group
from src.player_analytics import DEFINITIONS, aggregate_player, match_players


def read_document(root, relative, manifest):
    """Hash original bytes before parsing, making the actual inputs identifiable."""
    path = root / relative
    content = path.read_bytes() if path.exists() else gzip.decompress(path.with_suffix('.json.gz').read_bytes())
    manifest[relative] = hashlib.sha256(content).hexdigest()
    return json.loads(content)


def prepare(root, competition, season, *, minimum_minutes=450, minimum_samples=20):
    """Pool provider-ID/team contributions over the entire available catalogue.

    A missing selected event or lineup file suppresses every context's rates:
    an unseen appearance cannot be inferred to be absence. Team stints stay
    separate on transfers. Missing minutes within a known stint propagate via
    aggregate_player. xT is deliberately not fitted, loaded or benchmarked.
    """
    if (not finite_number(minimum_minutes) or minimum_minutes < 0
            or isinstance(minimum_samples, bool) or not isinstance(minimum_samples, int) or minimum_samples < 1):
        raise ValueError('Invalid cohort policy')
    root = Path(root)
    manifest = {}
    for name in ('README.md', 'LICENSE.pdf'):
        if (root / name).exists():
            manifest[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    catalogue = read_document(root, f'matches/{competition}/{season}.json', manifest)
    ids = [row['match_id'] for row in catalogue]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError('Empty or duplicated match catalogue')
    grouped = defaultdict(list)
    missing, match_audit = [], []
    for match in sorted(catalogue, key=lambda row: (row['match_date'], row['match_id'])):
        match_id = match['match_id']
        absent = [f'{kind}/{match_id}.json' for kind in ('events', 'lineups')
                  if not (root / kind / f'{match_id}.json').exists()
                  and not (root / kind / f'{match_id}.json.gz').exists()]
        if absent:
            missing.extend(absent)
            continue
        raw_events = read_document(root, f'events/{match_id}.json', manifest)
        raw_lineups = read_document(root, f'lineups/{match_id}.json', manifest)
        events = pd.DataFrame([flatten_event(row, True) for row in raw_events])
        lineups = pd.DataFrame([{'team_id': team['team_id'], 'team': team['team_name'],
            'player_id': player['player_id'], 'player': player['player_name'],
            'positions': player.get('positions'), 'cards': player.get('cards')}
            for team in raw_lineups for player in team['lineup']])
        expected_teams = {match[side]['home_team_id' if side == 'home_team' else 'away_team_id']
                          for side in ('home_team', 'away_team')}
        actual_teams = set(lineups.get('team_id', []))
        if expected_teams != actual_teams:
            missing.append(f'lineup_team_coverage/{match_id}')
        metadata = {**match, 'home_team': match['home_team']['home_team_name'],
                    'away_team': match['away_team']['away_team_name']}
        statuses = Counter()
        for team_id in sorted(expected_teams):
            players = match_players(events, lineups, metadata, team_id, None, None)
            for player_id, row in sorted(players.items()):
                grouped[(team_id, player_id)].append(row)
                statuses[row['minutes_status']] += 1
        match_audit.append({'match_id': match_id, 'lineup_teams': sorted(actual_teams),
                            'minutes_status_counts': dict(sorted(statuses.items()))})
    players = []
    for (team_id, player_id), rows in sorted(grouped.items()):
        aggregate = aggregate_player(rows, incomplete_collection=bool(missing))
        group = position_group(rows)
        eligible = (group is not None and aggregate['minutes'] is not None
                    and aggregate['minutes'] > 0 and aggregate['minutes'] >= minimum_minutes)
        players.append({'competition_id': competition, 'season_id': season,
            'team_id': team_id, 'player_id': player_id,
            'aliases': sorted({name for row in rows for name in row['aliases']}),
            'group': group, 'eligible': eligible,
            'match_ids': [row['match_id'] for row in rows],
            'position_histories': [{'match_id': row['match_id'], 'history': row['position_history']}
                                   for row in rows],
            'aggregate': aggregate})
    cohorts = []
    for group in POSITION_GROUPS:
        eligible = [row for row in players if row['group'] == group and row['eligible']]
        coverage = {metric: sum(row['aggregate']['comparison_evidence'][metric]['per90'] is not None
                               for row in eligible) for metric in BENCHMARK_METRICS}
        cohorts.append({'group': group, 'eligible_contexts': len(eligible),
            'eligible_player_ids': sorted({row['player_id'] for row in eligible}),
            'metric_samples': coverage,
            'ready_metrics': sorted(key for key, count in coverage.items() if count >= minimum_samples)})
    implementation = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                      for name in ('benchmark_prepare.py', 'benchmarks.py', 'player_analytics.py',
                                   'player_comparison.py', 'playing_time.py', 'metrics.py', 'progressive.py')}
    revision_file = root / 'revision.txt'
    identity = {'manifest': dict(sorted(manifest.items())), 'implementation_sha256': implementation,
                'upstream_revision': revision_file.read_text().strip() if revision_file.exists() else None,
                'dependencies': {name: version(name) for name in ('statsbombpy', 'pandas')},
                'competition_id': competition,
                'season_id': season, 'minimum_minutes': minimum_minutes, 'minimum_samples': minimum_samples,
                'schema_version': 'benchmark-v1', 'position_policy': 'unanimous-broad-group-v1',
                'missing_files': sorted(missing)}
    dataset_version = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return {**identity, 'dataset_version': dataset_version, 'definitions': DEFINITIONS,
        'match_ids': sorted(ids), 'matches': match_audit, 'players': players, 'cohorts': cohorts,
        'summary': {'player_contexts': len(players), 'unique_players': len({row['player_id'] for row in players}),
            'teams': len({row['team_id'] for row in players}),
            'ambiguous_or_missing_position_contexts': sum(row['group'] is None for row in players),
            'unknown_minutes_contexts': sum(row['aggregate']['minutes'] is None for row in players)}}


def feasibility(result):
    """Small reviewable evidence report; detailed player histories stay outside Git.

    Sensitivity tables reuse the same aggregates, so changing policy does not
    change recorded counts. Counts describe player/team contexts, not a league.
    """
    policies = []
    for minutes in (180, 450, 900):
        cohorts = []
        for group in POSITION_GROUPS:
            eligible = [row for row in result['players'] if row['group'] == group
                        and row['aggregate']['minutes'] is not None
                        and row['aggregate']['minutes'] > 0 and row['aggregate']['minutes'] >= minutes]
            coverage = {metric: sum(row['aggregate']['comparison_evidence'][metric]['per90'] is not None
                                   for row in eligible) for metric in BENCHMARK_METRICS}
            cohorts.append({'group': group, 'eligible_contexts': len(eligible), 'metric_samples': coverage,
                'ready_at_10': sorted(key for key, count in coverage.items() if count >= 10),
                'ready_at_20': sorted(key for key, count in coverage.items() if count >= 20)})
        policies.append({'minimum_minutes': minutes, 'cohorts': cohorts})
    return {key: value for key, value in result.items() if key not in ('players', 'definitions')} | {
        'policy_sensitivity': policies,
        'minutes_status_counts': dict(sorted(sum((Counter(row['minutes_status_counts']) for row in result['matches']), Counter()).items())),
        'metric_coverage': {metric: sum(row['aggregate']['comparison_evidence'][metric]['per90'] is not None
                                      for row in result['players']) for metric in BENCHMARK_METRICS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data_root', type=Path)
    parser.add_argument('--competition', type=int, required=True)
    parser.add_argument('--season', type=int, required=True)
    parser.add_argument('--minimum-minutes', type=float, default=450)
    parser.add_argument('--minimum-samples', type=int, default=20)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    args = parser.parse_args()
    result = prepare(args.data_root, args.competition, args.season,
                     minimum_minutes=args.minimum_minutes, minimum_samples=args.minimum_samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf8')
    if args.summary_output:
        args.summary_output.write_text(json.dumps(feasibility(result), indent=2, allow_nan=False) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
