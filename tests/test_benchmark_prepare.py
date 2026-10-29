"""Offline raw-file integration: identities, pooling, provenance and failures."""
import gzip
import json

import pytest

from src.benchmark_prepare import prepare, feasibility


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf8')


def fixture(root, *, matches=2):
    """Two complete synthetic squads, with duplicate display names across IDs."""
    catalogue = []
    for mid in range(1, matches + 1):
        catalogue.append({'match_id': mid, 'match_date': f'2024-01-0{mid}',
            'home_team': {'home_team_id': 10, 'home_team_name': 'A'},
            'away_team': {'away_team_id': 20, 'away_team_name': 'B'}})
        events, lineups = [], []
        for team_id, name in [(10, 'A'), (20, 'B')]:
            ids = range(team_id * 10, team_id * 10 + 11)
            team = {'id': team_id, 'name': name}
            def event(kind, period, clock, **fields):
                return {'type': {'name': kind}, 'period': period, 'timestamp': clock,
                        'team': team, **fields}
            events += [event('Starting XI', 1, '00:00:00', tactics={'lineup': [
                {'player': {'id': pid, 'name': 'Same name'}} for pid in ids]})]
            for period in (1, 2):
                events += [event('Half Start', period, '00:00:00'), event('Half End', period, '00:45:00')]
            events += [event('Shot', 1, '00:10:00', player={'id': team_id * 10, 'name': 'Same name'},
                             shot={'outcome': {'name': 'Saved'}, 'statsbomb_xg': .2})]
            lineups.append({'team_id': team_id, 'team_name': name, 'lineup': [
                {'player_id': pid, 'player_name': 'Same name', 'cards': [],
                 'positions': [{'position_id': 14, 'position': 'Center Midfield',
                                'start_reason': 'Starting XI', 'end_reason': 'Final Whistle'}]}
                for pid in ids]})
        write(root, f'events/{mid}.json', events)
        write(root, f'lineups/{mid}.json', lineups)
    write(root, 'matches/1/1.json', catalogue)


def test_deterministic_raw_build_and_compressed_equivalence(tmp_path):
    fixture(tmp_path)
    result = prepare(tmp_path, 1, 1, minimum_minutes=180, minimum_samples=20)
    assert result == prepare(tmp_path, 1, 1, minimum_minutes=180, minimum_samples=20)
    assert result['summary']['player_contexts'] == 22  # Names never merge IDs.
    player = result['players'][0]
    assert player['aggregate']['minutes'] == 180
    assert player['aggregate']['comparison_evidence']['shots']['per90'] == 1
    assert player['aggregate']['statistics']['xg'] == pytest.approx(.4)
    assert player['aggregate']['statistics']['xt_net'] is None
    assert len(result['manifest']) == 5
    assert result['cohorts'][3]['eligible_contexts'] == 22
    path = tmp_path / 'events/1.json'
    path.with_suffix('.json.gz').write_bytes(gzip.compress(path.read_bytes()))
    path.unlink()
    assert prepare(tmp_path, 1, 1, minimum_minutes=180, minimum_samples=20) == result
    assert feasibility(result)['minutes_status_counts'] == {'verified': 44}


@pytest.mark.parametrize('kind', ['events', 'lineups'])
def test_missing_file_blocks_rates_instead_of_dropping_exposure(tmp_path, kind):
    fixture(tmp_path)
    (tmp_path / kind / '2.json').unlink()
    result = prepare(tmp_path, 1, 1, minimum_minutes=1)
    assert result['missing_files'] == [f'{kind}/2.json']
    assert all(row['aggregate']['per90']['shots'] is None for row in result['players'])
    assert all(not row['eligible'] for row in result['players'])


def test_policy_changes_version_and_unknown_minutes_propagate(tmp_path):
    fixture(tmp_path)
    baseline = prepare(tmp_path, 1, 1, minimum_minutes=1)
    policy = prepare(tmp_path, 1, 1, minimum_minutes=900)
    assert baseline['dataset_version'] != policy['dataset_version']
    path = tmp_path / 'events/2.json'
    rows = json.loads(path.read_text())
    rows.append({'type': {'name': 'Player Off'}, 'team': {'id': 10, 'name': 'A'},
                 'player': {'id': 100, 'name': 'Same name'}, 'period': 1, 'timestamp': '00:20:00'})
    write(tmp_path, 'events/2.json', rows)
    result = prepare(tmp_path, 1, 1, minimum_minutes=1)
    player = result['players'][0]
    assert player['aggregate']['minutes'] is None
    assert player['aggregate']['known_minutes'] == 90
    assert player['aggregate']['per90']['shots'] is None
    assert not player['eligible']
    assert baseline['dataset_version'] != result['dataset_version']


def test_transfer_keeps_team_stints_and_partial_xg(tmp_path):
    fixture(tmp_path, matches=2)
    path = tmp_path / 'lineups/2.json'
    lineups = json.loads(path.read_text())
    lineups[0]['lineup'][0]['player_id'] = 999  # Replacement after player 100 moved.
    lineups[1]['lineup'][0]['player_id'] = 100
    write(tmp_path, 'lineups/2.json', lineups)
    path = tmp_path / 'events/2.json'
    rows = json.loads(path.read_text())
    for row in rows:
        replacement = 999 if row['team']['id'] == 10 else 100
        if row['type']['name'] == 'Starting XI':
            row['tactics']['lineup'][0]['player']['id'] = replacement
        if row['type']['name'] == 'Shot':
            row['player']['id'] = replacement
            if row['team']['id'] == 20:
                del row['shot']['statsbomb_xg']
    write(tmp_path, 'events/2.json', rows)
    result = prepare(tmp_path, 1, 1, minimum_minutes=1)
    stints = [row for row in result['players'] if row['player_id'] == 100]
    assert len(stints) == 2
    assert {row['team_id'] for row in stints} == {10, 20}
    assert stints[0]['match_ids'] == [1]
    assert stints[1]['match_ids'] == [2]
    assert stints[0]['aggregate']['comparison_evidence']['xg']['per90'] == .2
    assert stints[1]['aggregate']['comparison_evidence']['xg']['per90'] is None
