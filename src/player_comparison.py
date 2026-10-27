"""Comparison qualification over existing aggregates, without player ratings."""

# Each row retains its natural unit. There is no combined score, percentile,
# inferred primary position, or arithmetic between different football metrics.
METRICS = (
    ('passes', 'Pass attempts', 'observed', 'passes'),
    ('completed_passes', 'Completed passes', 'observed', 'passes'),
    ('completed_progressive_passes', 'Completed progressive passes', 'geometry', 'completed_progressive_passes'),
    ('shots', 'Shots', 'observed', 'shots'),
    ('goals', 'Shot goals', 'observed', 'shots'),
    ('successful_dribbles', 'Successful dribbles', 'observed', 'successful_dribbles'),
    ('successful_interceptions', 'Successful interceptions', 'observed', 'successful_interceptions'),
    ('xg', 'Provider xG estimate', 'provider_estimate', 'xg'),
    ('xt_positive', 'Experimental positive xT estimate', 'experimental_estimate', 'xt'),
    ('xt_net', 'Experimental net xT estimate', 'experimental_estimate', 'xt'),
)


def comparison_evidence(aggregate: dict, definitions: dict, *, incomplete_collection: bool) -> dict:
    """Qualify shared totals/rates for a same-context selected-match comparison.

    Inputs are the existing Python aggregate and definitions; values are never
    recalculated or ranked. Matching selected files does not imply matching
    minutes, roles or opportunity. Per90 already pools counts/exposure: two shots
    in 30 minutes plus one in 90 gives 2.25, not the mean of 6 and 1.

    Covered-only totals stay inspectable numerically, but partial xG, any unrated
    xT attempt, missing progression geometry or missing selected files withhold
    bars and comparison rates. Requiring full recorded coverage avoids inventing
    an arbitrary 'good enough' threshold. Unsuccessful moves can be intentionally
    unrated; a withheld xT bar is not evidence of zero value. Even fully rated xT
    remains an experimental estimate, not a complete account of player ability.
    A genuine measured/modelled zero remains zero; unknown never becomes zero.
    """
    statistics = aggregate['statistics']
    rows = {}
    for metric, label, kind, definition_key in METRICS:
        total = statistics[metric]
        status = 'complete'
        numerator = denominator = None
        note = 'Recorded contributions in the included files; different minutes and roles can explain differences.'
        if kind == 'geometry':
            numerator, denominator = statistics['progressive_valid_geometry'], statistics['passes']
            if numerator < denominator:
                status = 'geometry_partial'
                note = 'Qualifying count covers valid passing geometry only; unknown geometry is not nonprogressive.'
        elif kind == 'provider_estimate':
            numerator, denominator = statistics['shots_with_xg'], statistics['shots']
            if numerator < denominator:
                status = 'covered_shots_only'
            note = 'Sum of covered provider probabilities only; incomplete shot coverage withholds bars and comparison per90.'
        elif kind == 'experimental_estimate':
            numerator, denominator = statistics['xt_rated_actions'], statistics['xt_attempted_actions']
            if numerator < denominator:
                status = 'rated_moves_only'
            note = 'Experimental sum over rated moves only. Any unrated attempt, including unsuccessful/ineligible moves, withholds bars and comparison per90; not a player rating.'
        if total is None:
            status = 'unavailable'
            note += ' No covered value is available.'
        if incomplete_collection:
            status = 'partial_sample'
            note += ' A selected match is missing; these totals describe the included subset only.'
        rate = aggregate['per90'][metric] if status == 'complete' else None
        if rate is None:
            note += ' Comparison per90 requires complete coverage and valid positive minutes for the same numerator matches.'
        rows[metric] = {'label': label, 'kind': kind, 'definition': definitions[definition_key],
            'total': total, 'per90': rate, 'chart_total': total if status == 'complete' else None,
            'status': status, 'coverage_count': numerator, 'coverage_total': denominator, 'note': note}
    return rows
