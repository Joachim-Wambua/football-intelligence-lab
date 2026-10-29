"""Worked rank examples and conservative position policy, without live data."""
import pytest

from src.benchmarks import empirical_percentile, position_group, BENCHMARK_METRICS


def rank(value, reference, **kwargs):
    return empirical_percentile(value, reference, minutes=900, minimum_samples=1, **kwargs)


@pytest.mark.parametrize('value,expected', [(1, 12.5), (2, 50), (4, 87.5)])
def test_mid_distribution_ranks_and_ties(value, expected):
    assert rank(value, [1, 2, 2, 4])['percentile'] == expected


def test_constant_and_direction():
    assert rank(3, [3, 3, 3])['percentile'] == 50
    assert rank(1, [1, 2, 2, 4], higher_is_better=False)['percentile'] == 87.5
    assert rank(0, [0])['percentile'] == 50


@pytest.mark.parametrize('missing', [None, float('nan'), float('inf'), True])
def test_missing_is_not_zero(missing):
    assert rank(missing, [0, 1])['percentile'] is None
    assert rank(0, [0, missing])['sample_size'] == 1


def test_insufficient_samples_and_low_exposure():
    assert rank(2, [])['percentile'] is None
    assert rank(2, [None, float('nan')])['sample_size'] == 0
    assert empirical_percentile(2, [1, 2], minutes=450)['status'] == 'insufficient_samples'
    for minutes in [None, 0, -1, 449, float('inf')]:
        result = empirical_percentile(2, [1, 2], minutes=minutes, minimum_samples=2)
        assert result['status'] == 'low_exposure'
        assert result['percentile'] is None
    assert empirical_percentile(2, [1, 2], minutes=450, minimum_samples=2)['status'] == 'available'


@pytest.mark.parametrize('policy', [{'minimum_minutes': -1}, {'minimum_samples': 0},
                                    {'minimum_samples': 1.5}, {'higher_is_better': 'yes'}])
def test_invalid_policy(policy):
    with pytest.raises(ValueError):
        empirical_percentile(2, [1, 2], minutes=900, **policy)


def contribution(*ids, appeared=True):
    return {'appeared': appeared, 'position_history': [{'position_id': value} for value in ids]}


def test_roles_require_history_agreement():
    assert position_group([contribution(3, 4), contribution(5)]) == 'centre_back'
    assert position_group([contribution(3), contribution(2)]) is None
    assert position_group([contribution(3), contribution()]) is None
    assert position_group([contribution(99)]) is None
    assert position_group([contribution(3), contribution(appeared=False)]) == 'centre_back'
    assert position_group([contribution(3), contribution(appeared=None)]) is None
    assert position_group([contribution(18, 20)]) == 'midfield'
    assert not any(metric.startswith('xt') for metric in BENCHMARK_METRICS)


def test_contract_does_not_turn_unavailability_into_zero():
    from backend.api.benchmark_schemas import BenchmarkPercentile
    from pydantic import ValidationError
    record = dict(metric='shots', value_per90=None, percentile=None, sample_size=0,
                  status='unavailable', higher_is_better=True)
    assert BenchmarkPercentile(**record).percentile is None
    with pytest.raises(ValidationError):
        BenchmarkPercentile(**{**record, 'percentile': 0})
    with pytest.raises(ValidationError):
        BenchmarkPercentile(**{**record, 'status': 'available'})
