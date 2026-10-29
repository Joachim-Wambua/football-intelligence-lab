"""Offline benchmark policy and empirical ranks; no HTTP or model fitting."""
from math import isfinite
from numbers import Real

from src.player_analytics import RATE_METRICS

BENCHMARK_METRICS = tuple(key for key in RATE_METRICS if not key.startswith('xt_'))
POSITION_GROUPS = {
    'goalkeeper': {1}, 'centre_back': {3, 4, 5},
    'full_back': {2, 6, 7, 8}, 'midfield': set(range(9, 17)) | {18, 19, 20},
    'wide_forward': {17, 21}, 'striker': {22, 23, 24, 25},
}


def finite_number(value):
    """Booleans, NaN and infinities are not measurements."""
    return isinstance(value, Real) and not isinstance(value, bool) and isfinite(value)


def position_group(contributions):
    """Require all appeared-match histories to agree on one broad role group.

    This conservative policy uses actual provider IDs, not names or event touch
    locations. Multiple roles within one group are allowed; cross-group changes,
    missing histories and unknown participation remain unassigned. No primary
    position or time-in-role is inferred from nominal lineup clocks.
    """
    groups = set()
    for row in contributions:
        if row['appeared'] is False:
            continue
        history = row['position_history']
        if row['appeared'] is None or not history:
            return None
        for spell in history:
            group = next((name for name, ids in POSITION_GROUPS.items()
                          if spell.get('position_id') in ids), None)
            if group is None:
                return None
            groups.add(group)
    return next(iter(groups)) if len(groups) == 1 else None


def empirical_percentile(value, reference, *, minutes, minimum_minutes=450,
                         minimum_samples=20, higher_is_better=True):
    """Mid-distribution empirical percentile in an EXPLICIT eligible population.

    Reference contains one finite, qualified per90 per eligible player/team
    context, including the target when it is a member. Missing reference values
    are excluded, never imputed. P=100*(count(x<v)+0.5*count(x=v))/n.
    Thus [1,2,2,4] gives 50 for 2; constant distributions give 50. A lower-is-better
    metric uses 100-P. Exact numeric equality defines ties, without rounding.
    These are descriptive ranks, not confidence or ability probabilities.
    Exposure/sample thresholds are policy choices, not statistical guarantees.
    """
    if (not finite_number(minimum_minutes) or minimum_minutes < 0
            or isinstance(minimum_samples, bool) or not isinstance(minimum_samples, int)
            or minimum_samples < 1 or not isinstance(higher_is_better, bool)):
        raise ValueError('Invalid percentile policy')
    population = [float(item) for item in reference if finite_number(item)]
    result = {'percentile': None, 'sample_size': len(population), 'status': 'unavailable'}
    if not finite_number(value):
        return result
    if not finite_number(minutes) or minutes <= 0 or minutes < minimum_minutes:
        return {**result, 'status': 'low_exposure'}
    if len(population) < minimum_samples:
        return {**result, 'status': 'insufficient_samples'}
    # Half of each tie mass avoids arbitrary ordering among equal observations.
    rank = 100 * (sum(item < value for item in population)
                  + .5 * sum(item == value for item in population)) / len(population)
    return {**result, 'percentile': rank if higher_is_better else 100 - rank, 'status': 'available'}
