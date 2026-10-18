import json
import numpy as np
import pandas as pd
import pytest
from src.expected_threat import XTConfig, zone, extract_actions, fit, rate_actions, save_model, load_model


def events():
    return pd.DataFrame([
        dict(type='Pass', location=[10, 40], pass_end_location=[110, 40]),
        dict(type='Pass', location=[10, 40], pass_end_location=[110, 40], pass_outcome='Incomplete'),
        dict(type='Shot', location=[110, 40], shot_outcome='Goal'),
        dict(type='Shot', location=[110, 40], shot_outcome='Saved'),
        dict(type='Carry', location=[110, 40], carry_end_location=[10, 40]),
    ])


def test_zones():
    c = XTConfig(2, 2)
    assert [zone(x, c) for x in ([0,0], [60,0], [0,40], [120,80])] == [0,1,2,3]
    assert zone([0,0], c, 'left') == 3
    with pytest.raises(ValueError): zone([1,2], c, 'unknown')


@pytest.mark.parametrize('p', [None, [], [1], [1,2,3], [True,2], ['1',2], [-1,2], [121,2], [1,81], [float('nan'),2], [float('inf'),2]])
def test_invalid(p):
    assert zone(p) is None


@pytest.mark.parametrize('kwargs', [dict(nx=0), dict(ny=True), dict(max_iterations=0), dict(tolerance=float('nan'))])
def test_config(kwargs):
    with pytest.raises(ValueError): XTConfig(**kwargs)


def test_probabilities_convergence_and_negative_scores(tmp_path):
    c = XTConfig(2,1)
    e = events()
    model = fit(extract_actions(e,c),c)
    d = model['diagnostics']
    assert d['transition_row_sums'] == [0.5,1.0]
    assert np.array(d['p_shot'])+d['p_move'] == pytest.approx([1,1])
    assert model['surface'][0] == pytest.approx([.2,.4])
    assert d['residuals'][-1] <= c.tolerance
    rated = rate_actions(e,model)
    assert rated.xT.iloc[0] == pytest.approx(.2)
    assert pd.isna(rated.xT.iloc[1]) and pd.isna(rated.xT.iloc[2])
    assert rated.xT.iloc[4] == pytest.approx(-.2)
    path = tmp_path/'model.json'
    save_model(model,path)
    assert load_model(path) == model
    model['surface'] = [[float('nan'),0]]
    path.write_text(json.dumps(model))
    with pytest.raises(ValueError): load_model(path)


def test_empty_zones_and_invalid_end():
    c = XTConfig(2,1)
    e = pd.DataFrame([dict(type='Pass',location=[1,2],pass_end_location=None),
                      dict(type='Shot',location=[110,40],shot_outcome=None)])
    model = fit(extract_actions(e,c),c)
    assert model['surface'] == [[0,0]]
    assert model['diagnostics']['unobserved_zones'] == 1
    assert rate_actions(e,model).xT.isna().all()
    empty = fit(extract_actions(pd.DataFrame(),c),c)
    assert empty['diagnostics']['unobserved_zones'] == 2


def test_nonconvergence_and_shootouts():
    with pytest.raises(RuntimeError):
        c = XTConfig(2,1,max_iterations=1)
        fit(extract_actions(events(),c),c)
    e = events().assign(period=5)
    assert extract_actions(e).empty


def test_empty_move_cycle_and_terminal_shots():
    c = XTConfig(2, 1)
    cyclic = pd.DataFrame([
        dict(type='Carry', location=[10, 40], carry_end_location=[110, 40]),
        dict(type='Carry', location=[110, 40], carry_end_location=[10, 40])])
    model = fit(extract_actions(cyclic, c), c)
    assert model['surface'] == [[0, 0]]
    assert model['diagnostics']['transition_row_sums'] == [1, 1]
    assert model['diagnostics']['iterations'] == 1
    shots = pd.DataFrame([dict(type='Shot', location=[110, 40], shot_outcome='Goal')])
    model = fit(extract_actions(shots, c), c)
    assert model['surface'] == [[0, 1]]


def test_carry_uses_own_endpoint_and_preserves_duplicate_indices():
    c = XTConfig(2, 1)
    model = fit(extract_actions(events(), c), c)
    e = pd.DataFrame([
        dict(type='Carry', location=[110, 40], carry_end_location=[10, 40]),
        dict(type='Carry', location=[10, 40]),  # not inferred from next event
        dict(type='Pass', location=[110, 40], pass_end_location=[110, 40]),
        dict(type='Carry', location=[110, 40], carry_end_location=[10, 40], period=5),
    ], index=[9, 9, 1, 9])
    original = e.copy(deep=True)
    rated = rate_actions(e, model)
    assert rated.index.tolist() == [9, 9, 1, 9]
    assert rated.xT.iloc[0] == pytest.approx(-.2)
    assert pd.isna(rated.xT.iloc[1])
    assert rated.xT.iloc[2] == 0  # defined same-zone value, not missing
    assert pd.isna(rated.xT.iloc[3])
    pd.testing.assert_frame_equal(e, original)


def test_direction_rotation_and_invalid_declarations():
    c = XTConfig(2, 1)
    right = events()
    left = right.copy(deep=True)
    for col in ['location', 'pass_end_location', 'carry_end_location']:
        left[col] = left[col].map(lambda p: [120-p[0], 80-p[1]] if isinstance(p, list) else p)
    a = fit(extract_actions(right, c, 'right'), c)
    b = fit(extract_actions(left, c, 'left'), c)
    assert np.allclose(a['surface'], b['surface'])
    assert rate_actions(left, b, 'left').xT.iloc[0] == pytest.approx(.2)
    with pytest.raises(ValueError): extract_actions(pd.DataFrame(), direction=None)
    with pytest.raises(ValueError): extract_actions(pd.DataFrame([{'bad': 1}]))
    with pytest.raises(ValueError): fit(extract_actions(right, c), XTConfig(4, 1))
    with pytest.raises(ValueError): fit(pd.DataFrame())


def test_nullable_and_malformed_outcomes():
    c = XTConfig(2, 1)
    e = pd.DataFrame([
        dict(type='Pass', location=[10, 40], pass_end_location=[110, 40], pass_outcome=pd.NA, period=pd.NA),
        dict(type='Pass', location=[10, 40], pass_end_location=[110, 40], pass_outcome=['Incomplete']),
        dict(type='Shot', location=[110, 40], shot_outcome=pd.NA),
        dict(type=pd.NA, location=[110, 40]),
    ])
    a = extract_actions(e, c)
    assert a.success.tolist() == [True, False, False]
    assert a.eligible.tolist() == [True, False, False]
    assert fit(a, c)['diagnostics']['excluded'] == 2


@pytest.mark.parametrize('outcome', ['Incomplete', 'Out', 'Pass Offside', 'Unknown', 'Injury Clearance'])
def test_no_destination_credit_for_explicit_pass_outcome(outcome):
    c = XTConfig(2, 1)
    model = fit(extract_actions(events(), c), c)
    e = pd.DataFrame([dict(type='Pass', location=[10, 40], pass_end_location=[110, 40], pass_outcome=outcome)])
    assert rate_actions(e, model).xT.isna().all()
    d = fit(extract_actions(e, c), c)['diagnostics']
    assert d['moves'] == [1, 0]
    assert d['transition_row_sums'] == [0, 0]


def test_serialization_rejects_version_and_shape(tmp_path):
    c = XTConfig(2, 1)
    model = fit(extract_actions(events(), c), c)
    for key, bad_value in [('version', 2), ('version', True), ('surface', [[0]]),
                           ('surface', [[-1, 0]]), ('surface', [[2, 0]]),
                           ('surface', [[float('inf'), 0]])]:
        bad = {**model, key: bad_value}
        with pytest.raises(ValueError): save_model(bad, tmp_path/'bad.json')
        with pytest.raises(ValueError): rate_actions(events(), bad)


def _raw_match(goal=False):
    return [
        {'id': '1', 'type': {'name': 'Pass'}, 'period': 1, 'team': {'name': 'A'},
         'player': {'name': 'P'}, 'location': [10, 40], 'pass': {'end_location': [110, 40]}},
        {'id': '2', 'type': {'name': 'Shot'}, 'period': 2, 'team': {'name': 'A'},
         'location': [110, 40], 'shot': {'outcome': {'name': 'Goal' if goal else 'Saved'}}},
        {'id': '3', 'type': {'name': 'Half End'}, 'period': 1},
        {'id': '4', 'type': {'name': 'Half End'}, 'period': 2},
    ]


def _dataset(tmp_path):
    (tmp_path/'matches'/'9').mkdir(parents=True)
    (tmp_path/'events').mkdir()
    manifest = [{'match_id': i, 'match_date': f'2024-01-0{i}', 'match_status': 'available'} for i in [3, 1, 2, 4]]
    (tmp_path/'matches'/'9'/'281.json').write_text(json.dumps(manifest), encoding='utf-8')
    for i in [1, 2, 3]:
        (tmp_path/'events'/f'{i}.json').write_text(json.dumps(_raw_match(goal=i == 1)), encoding='utf-8')


def test_pipeline_selection_no_leakage_and_report(tmp_path):
    from src.xt_research import train, report
    _dataset(tmp_path)
    c = XTConfig(2, 1)
    model, held = train(tmp_path, 9, 281, limit=3, held_out=1, config=c)
    assert model['metadata']['train_ids'] == [1, 2]
    assert model['metadata']['held_out_ids'] == [3]
    assert model['metadata']['missing_available_files'] == 1
    assert model['metadata']['published_matches'] == 4
    assert model['diagnostics']['actions'] == 4
    assert held.match_id.unique().tolist() == [3]
    # Different outcomes in held-out data must not change the fitted surface.
    (tmp_path/'events'/'3.json').write_text(json.dumps(_raw_match(goal=True)), encoding='utf-8')
    changed, _ = train(tmp_path, 9, 281, 3, 1, c)
    assert changed['surface'] == model['surface']
    assert changed['metadata']['event_sha256']['3'] != model['metadata']['event_sha256']['3']
    report(model, held, tmp_path/'report')
    assert (tmp_path/'report'/'xt_research.png').stat().st_size > 0
    assert 'xT' in pd.read_csv(tmp_path/'report'/'selected_passes.csv')
    # Timestamp changes only; deterministic fitting and selection.
    repeated, _ = train(tmp_path, 9, 281, 3, 1, c)
    assert repeated['diagnostics'] == changed['diagnostics']


def test_pipeline_rejects_incomplete_files_and_bad_split(tmp_path):
    from src.xt_research import train
    _dataset(tmp_path)
    with pytest.raises(ValueError): train(tmp_path, 9, 281, limit=2, held_out=1)
    with pytest.raises(ValueError): train(tmp_path, 9, 281, limit=-1)
    bad = _raw_match()[:-1]
    (tmp_path/'events'/'1.json').write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='Half End'): train(tmp_path, 9, 281, 3, 1)
