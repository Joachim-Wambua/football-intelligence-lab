"""Natural-unit comparisons over matched files, without a reference population."""
import pytest
from src.player_analytics import aggregate_player, COUNT_METRICS, NULLABLE_METRICS
from test_player_intelligence import player_client, player_source, BASE, QUERY


def contribution(match_id=1, minutes=30, **statistics):
    """Synthetic known exposure; the real lifecycle algorithm is tested separately."""
    return {'match_id': match_id, 'minutes': minutes, 'appeared': True,
        'statistics': {**dict.fromkeys(COUNT_METRICS, 0), **dict.fromkeys(NULLABLE_METRICS, None), **statistics}}


def test_matched_numerator_and_pooled_exposure_are_not_mean_rates():
    result = aggregate_player([contribution(1, 30, shots=2), contribution(2, 90, shots=1)])
    metric = result['comparison_evidence']['shots']
    assert result['per90_match_ids'] == [1, 2]
    assert result['minutes'] == 120
    assert metric['total'] == metric['chart_total'] == 3
    assert metric['per90'] == 2.25  # 90*(2+1)/(30+90), not mean(6,1).
    assert metric['kind'] == 'observed'
    assert metric['definition']


@pytest.mark.parametrize('minutes', [None, 0, -1, float('inf')])
def test_invalid_or_zero_minutes_do_not_turn_counts_into_rates(minutes):
    result = aggregate_player([contribution(minutes=minutes, shots=0)])
    metric = result['comparison_evidence']['shots']
    assert metric['total'] == metric['chart_total'] == 0
    assert metric['per90'] is None
    assert result['per90_match_ids'] == []


def test_missing_one_exposure_blocks_pooled_rates_for_the_whole_numerator():
    result = aggregate_player([contribution(1, 90, shots=2), contribution(2, None, shots=1)])
    assert result['comparison_evidence']['shots']['total'] == 3
    assert result['comparison_evidence']['shots']['per90'] is None
    assert result['known_minutes'] == 90


def test_partial_xg_retains_covered_sum_without_a_complete_comparison():
    result = aggregate_player([contribution(shots=3, shots_with_xg=1, xg=.2)])
    metric = result['comparison_evidence']['xg']
    assert metric['total'] == .2
    assert metric['coverage_count'] == 1 and metric['coverage_total'] == 3
    assert metric['status'] == 'covered_shots_only'
    assert metric['chart_total'] is None and metric['per90'] is None
    missing = aggregate_player([contribution(shots=3)])['comparison_evidence']['xg']
    assert missing['total'] is None and missing['status'] == 'unavailable'
    zero = aggregate_player([contribution(minutes=90, shots=1, shots_with_xg=1, xg=0)])['comparison_evidence']['xg']
    assert zero['chart_total'] == zero['per90'] == 0
    assert zero['kind'] == 'provider_estimate'


def test_signed_xt_and_zero_survive_full_recorded_coverage():
    result = aggregate_player([contribution(1, 30, xt_net=-.03, xt_positive=.01, xt_rated_actions=3, xt_attempted_actions=3),
        contribution(2, 90, xt_net=.01, xt_positive=.01, xt_rated_actions=2, xt_attempted_actions=2)])
    metric = result['comparison_evidence']['xt_net']
    assert metric['total'] == metric['chart_total'] == pytest.approx(-.02)
    assert metric['per90'] == pytest.approx(-.015)
    assert metric['kind'] == 'experimental_estimate'
    assert metric['coverage_count'] == metric['coverage_total'] == 5
    zero = aggregate_player([contribution(minutes=90, xt_net=0, xt_positive=0, xt_rated_actions=1, xt_attempted_actions=1)])
    assert zero['comparison_evidence']['xt_net']['chart_total'] == 0


def test_unrated_xt_withholds_comparison_even_when_existing_profile_rate_exists():
    result = aggregate_player([contribution(minutes=90, xt_net=-.02, xt_positive=.01, xt_rated_actions=1, xt_attempted_actions=3)])
    assert result['per90']['xt_net'] == -.02  # Preserve Sprint 8A's profile contract.
    metric = result['comparison_evidence']['xt_net']
    assert metric['total'] == -.02
    assert metric['status'] == 'rated_moves_only'
    assert metric['chart_total'] is None and metric['per90'] is None


def test_failed_selected_file_and_missing_geometry_remain_partial():
    result = aggregate_player([contribution(minutes=90, passes=5, progressive_valid_geometry=2, completed_progressive_passes=1)])
    metric = result['comparison_evidence']['completed_progressive_passes']
    assert metric['total'] == 1 and metric['status'] == 'geometry_partial'
    assert metric['chart_total'] is None and metric['per90'] is None
    result = aggregate_player([contribution(minutes=90, passes=5)], incomplete_collection=True)
    assert result['comparison_evidence']['passes']['total'] == 5
    assert result['comparison_evidence']['passes']['chart_total'] is None
    assert result['comparison_evidence']['passes']['status'] == 'partial_sample'


def test_catalogue_contains_two_id_distinct_aggregates_from_one_cached_scope(player_client, player_source):
    response = player_client.get(BASE + QUERY)
    assert response.status_code == 200, response.text
    data = response.json()
    same_names = [row for row in data['players'] if row['player'] == 'Same name']
    assert [row['player_id'] for row in same_names] == [1, 2]
    assert data['context']['included_match_ids'] == [1, 2]
    assert all(row['aggregate']['per90_match_ids'] == [1, 2] for row in same_names)
    assert same_names[0]['aggregate']['comparison_evidence']['passes']['total'] == 2
    assert same_names[1]['aggregate']['comparison_evidence']['passes']['total'] == 0
    before = (player_source.events.call_count, player_source.lineups.call_count)
    player_client.get(BASE + '/2' + QUERY)
    player_client.get(BASE + QUERY.replace('match_ids=1&match_ids=2', 'match_ids=2&match_ids=1'))
    assert (player_source.events.call_count, player_source.lineups.call_count) == before == (2, 2)


@pytest.mark.parametrize('query', [QUERY.replace('season_id=281', 'season_id=999'),
    QUERY.replace('team_id=10', 'team_id=999'), QUERY.replace('match_ids=2', 'match_ids=999')])
def test_comparison_scope_rejects_cross_context_requests(player_client, query):
    assert player_client.get(BASE + query).status_code == 404
