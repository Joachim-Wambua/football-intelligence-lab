"""Small lifecycle examples teach elapsed minutes and pooled per90 denominators."""
from copy import deepcopy
from unittest.mock import Mock

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.provider import CachedProvider, get_provider
from backend.api.player_service import PlayerCollectionService, get_player_service
from backend.api import player_routes
from src.playing_time import playing_time, clock_seconds, period_lengths
from src.player_analytics import match_players, aggregate_player, per90, COUNT_METRICS, NULLABLE_METRICS


def roster():
    return pd.DataFrame([{'team_id': 10, 'team': 'A', 'player_id': pid,
        'player': 'Same name' if pid in (1, 2) else f'Player {pid}',
        'positions': [{'position_id': 14, 'position': 'Center Midfield', 'from': '00:00', 'to': None,
            'from_period': 1, 'to_period': None, 'start_reason': 'Starting XI', 'end_reason': 'Final Whistle'}] if pid <= 11 else [], 'cards': []}
        for pid in range(1, 15)])


def event(kind, period, timestamp, **fields):
    return {'type': kind, 'team_id': 10, 'team': 'A', 'period': period, 'timestamp': timestamp, **fields}


def events(*additional, extra_time=False):
    rows = [event('Starting XI', 1, '00:00:00', tactics={'lineup': [{'player': {'id': pid}} for pid in range(1, 12)]}),
        event('Half Start', 1, '00:00:00'), event('Half End', 1, '00:47:00'),
        event('Half Start', 2, '00:00:00'), event('Half End', 2, '00:49:00'),
        event('Pass', 1, '00:10:00', player_id=1, player='Same name', location=[40, 40], pass_end_location=[60, 40]),
        event('Shot', 2, '00:10:00', player_id=2, player='Same name', location=[110, 40], shot_outcome='Goal', shot_statsbomb_xg=.3)]
    if extra_time:
        rows += [event('Half Start', 3, '00:00:00'), event('Half End', 3, '00:16:00'),
            event('Half Start', 4, '00:00:00'), event('Half End', 4, '00:17:00')]
    return pd.DataFrame([*rows, *additional])


MATCH = {'match_id': 1, 'match_date': '2024-01-01', 'home_team': 'A', 'away_team': 'B'}


def test_starters_late_and_halftime_substitutes_unused_and_duplicate_names():
    frame = events(event('Substitution', 2, '00:48:00', player_id=1, substitution_replacement_id=12),
        event('Substitution', 2, '00:00:00', player_id=3, substitution_replacement_id=13))
    timing = playing_time(frame, roster(), 10)
    assert timing[1]['minutes'] == 95  # 47 first-half + 48 second-half
    assert timing[12] == {'minutes': 1, 'appeared': True, 'minutes_status': 'verified'}
    assert timing[3]['minutes'] == 47
    assert timing[13]['minutes'] == 49  # Added time belongs to that player's half.
    assert timing[14] == {'minutes': 0, 'appeared': False, 'minutes_status': 'unused_substitute'}
    profiles = match_players(frame, roster(), MATCH, 10, None, None)
    assert profiles[1]['player'] == profiles[2]['player'] == 'Same name'
    assert profiles[1]['statistics']['passes'] == 1
    assert profiles[2]['statistics']['passes'] == 0
    assert profiles[2]['statistics']['shots'] == 1
    assert profiles[1]['statistics']['completed_progressive_passes'] == 1
    assert profiles[14]['per90']['passes'] is None


@pytest.mark.parametrize('column,card', [('foul_committed_card', 'Red Card'), ('bad_behaviour_card', 'Second Yellow')])
def test_dismissals_and_bench_cards(column, card):
    kind = 'Foul Committed' if column.startswith('foul') else 'Bad Behaviour'
    timing = playing_time(events(event(kind, 2, '00:20:00', player_id=1, **{column: card}),
        event('Bad Behaviour', 1, '00:12:00', player_id=14, bad_behaviour_card='Red Card')), roster(), 10)
    assert timing[1]['minutes'] == 67
    assert timing[14]['minutes'] == 0


def test_extra_time_periods_and_shootouts_are_separate():
    frame = events(event('Substitution', 3, '00:00:00', player_id=1, substitution_replacement_id=12),
        event('Shot', 5, '00:00:10', player_id=12, player='Player 12', shot_outcome='Goal', shot_statsbomb_xg=.8), extra_time=True)
    timing = playing_time(frame, roster(), 10)
    assert timing[1]['minutes'] == 96
    assert timing[12]['minutes'] == 33
    assert timing[2]['minutes'] == 129
    profiles = match_players(frame, roster(), MATCH, 10, None, None)
    assert profiles[12]['statistics']['shots'] == 0


@pytest.mark.parametrize('failure', ['lineups', 'end', 'short_end', 'conflict', 'xi', 'sub_id', 'negative_time', 'period'])
def test_missing_and_invalid_exposure_never_becomes_ninety(failure):
    frame, lineup = events(), roster()
    if failure == 'lineups': lineup = pd.DataFrame()
    if failure == 'end': frame = frame.loc[~(frame.type.eq('Half End') & frame.period.eq(2))]
    if failure == 'short_end': frame.loc[frame.type.eq('Half End') & frame.period.eq(2), 'timestamp'] = '00:20:00'
    if failure == 'conflict': frame = pd.concat([frame, pd.DataFrame([event('Half End', 2, '00:55:00')])])
    if failure == 'xi': frame = frame.loc[~frame.type.eq('Starting XI')]
    if failure == 'sub_id': frame = pd.concat([frame, pd.DataFrame([event('Substitution', 2, '00:20:00', player_id=1, substitution_replacement_id=999)])])
    if failure == 'negative_time': frame.loc[frame.type.eq('Half End'), 'timestamp'] = '-1:00:00'
    if failure == 'period': frame.loc[frame.type.eq('Pass'), 'period'] = None
    result = playing_time(frame, lineup, 10)
    assert result[1]['minutes'] is None
    assert result[1]['minutes_status'] not in ('verified', 'unused_substitute')


def test_temporary_absences_and_inconsistent_activity_are_qualified_per_player():
    frame = events(event('Player Off', 1, '00:20:00', player_id=1))
    result = playing_time(frame, roster(), 10)
    assert result[1]['minutes_status'] == 'temporary_absence_unsupported'
    assert result[2]['minutes'] == 96
    # An on-ball event does not turn a bench player into a guessed substitute.
    frame = events(event('Pass', 2, '00:20:00', player_id=14, player='Player 14'))
    assert playing_time(frame, roster(), 10)[14]['minutes'] is None


def test_period_end_duplicates_within_one_second_and_card_conflicts():
    frame = events(event('Half End', 2, '00:49:00.280'))
    assert playing_time(frame, roster(), 10)[2]['minutes'] == pytest.approx(96 + .28/60)
    lineup = roster()
    lineup.at[0, 'cards'] = [{'card_type': 'Red Card', 'period': 2, 'time': '60:00'}]
    assert playing_time(events(), lineup, 10)[1]['minutes_status'] == 'dismissal_event_missing'


@pytest.mark.parametrize('minutes', [None, 0, -1, float('nan'), float('inf'), True, '90'])
def test_invalid_per90_denominators(minutes):
    stats = dict.fromkeys(COUNT_METRICS, 0) | dict.fromkeys(NULLABLE_METRICS, None)
    assert all(value is None for value in per90(stats, minutes).values())


def test_pooled_rates_partial_minutes_and_missing_xg():
    frame = events(event('Shot', 1, '00:20:00', player_id=2, player='Same name', location=[100, 40]))
    own = match_players(frame, roster(), MATCH, 10, None, None)[2]
    assert own['statistics']['shots'] == 2
    assert own['statistics']['shots_with_xg'] == 1
    assert own['statistics']['xg'] == .3
    assert own['per90']['xg'] is None
    first, second = deepcopy(own), deepcopy(own)
    first.update(minutes=30, match_id=1); second.update(minutes=90, match_id=2)
    first['statistics']['shots'] = 2; second['statistics']['shots'] = 1
    aggregate = aggregate_player([first, second])
    assert aggregate['per90']['shots'] == 2.25
    second['minutes'] = None
    aggregate = aggregate_player([first, second])
    assert aggregate['known_minutes'] == 30
    assert aggregate['minutes'] is None
    assert aggregate['per90']['shots'] is None
    assert aggregate['per90_match_ids'] == []
    no_xg = match_players(events(), roster(), MATCH, 10, None, None)[1]
    assert no_xg['statistics']['xg'] is None
    assert no_xg['statistics']['xt_net'] is None


@pytest.fixture
def player_source():
    source = Mock()
    source.competitions.return_value = pd.DataFrame([{'competition_id': 9, 'season_id': 281}])
    source.matches.return_value = pd.DataFrame([MATCH, {**MATCH, 'match_id': 2, 'match_date': '2024-01-08'}])
    source.events.return_value = events()
    source.lineups.return_value = roster()
    return source


@pytest.fixture
def player_client(player_source, monkeypatch):
    provider = CachedProvider(player_source)
    service = PlayerCollectionService()
    app.dependency_overrides[get_provider] = lambda: provider
    app.dependency_overrides[get_player_service] = lambda: service
    def unavailable(): raise HTTPException(503, 'Model unavailable')
    monkeypatch.setattr(player_routes, 'get_xt_model', unavailable)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


QUERY = '?competition_id=9&season_id=281&team_id=10&match_ids=1&match_ids=2'
BASE = '/api/v1/player-intelligence/players'


def test_api_context_profiles_ids_nulls_and_shared_collection_cache(player_client, player_source):
    response = player_client.get(BASE + QUERY)
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data['players']) == 14
    assert [p['player_id'] for p in data['players'] if p['player'] == 'Same name'] == [1, 2]
    assert data['context']['included_match_ids'] == [1, 2]
    assert data['model']['status'] == 'unavailable'
    profile = player_client.get(BASE + '/1' + QUERY).json()
    assert profile['identity']['aggregate']['minutes'] == 192
    assert len(profile['matches']) == 2
    assert profile['identity']['aggregate']['statistics']['passes'] == 2
    assert profile['identity']['aggregate']['statistics']['xg'] is None
    assert profile['identity']['aggregate']['per90']['passes'] == pytest.approx(90*2/192)
    assert profile['matches'][0]['minutes_provenance']
    player_client.get(BASE + '/2' + QUERY)
    assert player_source.events.call_count == 2
    assert player_source.lineups.call_count == 2
    assert player_client.get(BASE + '/999' + QUERY).status_code == 404
    assert 'NaN' not in response.text and 'Infinity' not in response.text


@pytest.mark.parametrize('query', ['', '?competition_id=0&season_id=281&team_id=10&match_ids=1',
    '?competition_id=9&season_id=281&team_id=10&match_ids=0',
    '?competition_id=9&season_id=281&team_id=10&match_ids=1&match_ids=1',
    '?competition_id=9&season_id=281&team_id=10' + ''.join(f'&match_ids={i}' for i in range(1, 7))])
def test_api_selection_validation(player_client, query):
    assert player_client.get(BASE + query).status_code == 422


def test_api_missing_lineups_wrong_context_and_failed_match_coverage(player_client, player_source):
    player_source.lineups.side_effect = HTTPException(404, 'No file')
    player_source.events.side_effect = [events(), HTTPException(404, 'Missing')]
    response = player_client.get(BASE + '/1' + QUERY)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['context']['lineups_unavailable_match_ids'] == [1]
    assert data['context']['failed_matches'][0]['match_id'] == 2
    assert data['identity']['aggregate']['minutes'] is None
    assert data['matches'][0]['minutes_status'] == 'lineups_unavailable'
    assert player_client.get(BASE + QUERY.replace('match_ids=2', 'match_ids=999')).status_code == 404


def test_cache_expiry_and_snapshot_isolation(player_source):
    now = [0]
    service = PlayerCollectionService(timer=lambda: now[0])
    provider = CachedProvider(player_source)
    first = service.collection(provider, 9, 281, 10, [1], None)
    first['profiles'][1]['identity']['player'] = 'Mutated'
    second = service.collection(provider, 9, 281, 10, [1], None)
    assert second['profiles'][1]['identity']['player'] == 'Same name'
    assert len(service.cache) == 1
    now[0] = 901
    assert len(service.cache) == 0

def test_position_history_can_reveal_a_missing_no_touch_substitution():
    lineup = roster()
    lineup.at[11, 'positions'] = [{'position': 'Center Forward', 'start_reason': 'Substitution - On (Tactical)', 'end_reason': 'Final Whistle'}]
    assert playing_time(events(), lineup, 10)[12]['minutes_status'] == 'lineup_lifecycle_conflict'
    lineup.at[0, 'positions'] = [{'position': 'Center Forward', 'start_reason': 'Starting XI', 'end_reason': 'Substitution - Off (Tactical)'}]
    assert playing_time(events(), lineup, 10)[1]['minutes_status'] == 'substitution_event_missing'


def test_api_uses_frozen_xt_without_fitting(player_client, monkeypatch):
    from backend.api.xt_model import get_xt_model
    from src import expected_threat
    monkeypatch.setattr(player_routes, 'get_xt_model', get_xt_model)
    def forbidden(*args, **kwargs): raise AssertionError('Requests must not train')
    monkeypatch.setattr(expected_threat, 'fit', forbidden)
    response = player_client.get(BASE + '/1' + QUERY)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['model']['status'] == 'available'
    assert data['model']['model_id'] == data['matches'][0]['model_id']
    assert data['matches'][0]['statistics']['xt_rated_actions'] == 1
    assert data['matches'][0]['statistics']['xt_net'] is not None


def test_lineup_adapter_preserves_ids_and_optional_local_source(monkeypatch, tmp_path):
    from src import data_loader
    from src.datasets import LocalDatasetSource
    def lineups(**kwargs):
        assert kwargs == {'match_id': 1, 'fmt': 'dict'}
        return {10: {'team_id': 10, 'team_name': 'A', 'lineup': [
            {'player_id': 42, 'player_name': 'Name', 'positions': [], 'cards': []}]}}
    monkeypatch.setattr(data_loader.sb, 'lineups', lineups)
    table = data_loader.load_lineups(1)
    assert table.iloc[0].player_id == 42
    assert table.iloc[0].positions == []
    assert LocalDatasetSource(tmp_path).lineups(1).empty

def test_profiles_include_not_in_squad_without_inventing_an_appearance(player_source):
    player_source.events.side_effect = [events(event('Substitution', 2, '00:30:00', player_id=1, substitution_replacement_id=12)), events()]
    player_source.lineups.side_effect = [roster(), roster().loc[lambda table: ~table.player_id.eq(12)]]
    collection = PlayerCollectionService().collection(CachedProvider(player_source), 9, 281, 10, [1, 2], None)
    player = collection['profiles'][12]
    assert player['matches'][0]['minutes'] == 19
    assert player['matches'][1]['minutes_status'] == 'not_in_squad'
    assert player['matches'][1]['minutes'] == 0
    assert player['identity']['aggregate']['appearances'] == 1
    assert player['identity']['aggregate']['minutes'] == 19


def test_invalid_provider_player_ids_are_safe_http_errors(player_client, player_source):
    player_source.events.return_value.loc[player_source.events.return_value.type.eq('Pass'), 'player_id'] = 1.5
    response = player_client.get(BASE + QUERY)
    assert response.status_code == 502
    assert 'Invalid data returned by provider' in response.text

def test_missing_roster_preserves_no_touch_replacement_and_starter_identities():
    frame = events(event('Substitution', 2, '00:48:00', player_id=1,
        substitution_replacement_id=12, substitution_replacement='No touch substitute'))
    profiles = match_players(frame, pd.DataFrame(), MATCH, 10, None, None)
    assert len(profiles) == 12
    assert profiles[12]['player'] == 'No touch substitute'
    assert profiles[12]['appeared'] is True
    assert profiles[12]['minutes'] is None
    assert profiles[12]['statistics']['passes'] == 0
    assert profiles[11]['appeared'] is True
    assert profiles[11]['minutes_status'] == 'lineups_unavailable'

@pytest.mark.parametrize('invalid', [-1, float('nan'), float('inf'), True])
def test_aggregate_excludes_invalid_minutes_from_known_exposure(invalid):
    own = match_players(events(), roster(), MATCH, 10, None, None)[1]
    own['minutes'] = invalid
    aggregate = aggregate_player([own])
    assert aggregate['minutes'] is None
    assert aggregate['known_minutes'] is None
    assert aggregate['minutes_covered_matches'] == 0
    assert aggregate['per90']['passes'] is None
