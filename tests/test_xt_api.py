"""Signed movement values, empirical coverage and offline-only artifact serving."""
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from requests import Timeout

from backend.api.main import app
from backend.api.provider import CachedProvider, get_provider
from backend.api.xt_model import MODEL_PATH, get_xt_model, read_xt_model
from src.xt_summary import valued_moves, player_xt_summary


@pytest.fixture
def model_path(tmp_path):
    """Two zones make +0.3, -0.3 and zero behavior inspectable without training."""
    model = json.loads(MODEL_PATH.read_text(encoding='utf-8'))
    model['config'].update(nx=2, ny=1)
    model['surface'] = [[.1, .4]]
    model['diagnostics'].update(shots=[0, 2], goals=[0, 1])
    path = tmp_path / 'fixture-model.json'
    path.write_text(json.dumps(model), encoding='utf-8')
    return path


@pytest.fixture
def events():
    base = dict(team_id=10, team='A', player_id=100, player='P', type='Pass', period=1,
                location=[10, 40], pass_end_location=[110, 40])
    return pd.DataFrame([
        {**base, 'id': 'positive'},
        {**base, 'id': 'negative', 'type': 'Carry', 'location': [110, 40], 'carry_end_location': [10, 40]},
        {**base, 'id': 'zero', 'pass_end_location': [10, 40]},
        {**base, 'id': 'failed', 'pass_outcome': 'Incomplete'},
        {**base, 'id': 'missing', 'pass_end_location': None},
        {**base, 'id': 'unknown', 'player_id': 101, 'player': 'P', 'location': None},
        {**base, 'id': 'shot', 'type': 'Shot', 'shot_outcome': 'Goal'},
    ])


@pytest.fixture
def client(model_path, events):
    active = read_xt_model(model_path)
    source = Mock()
    source.events.return_value = events
    app.dependency_overrides[get_provider] = lambda: CachedProvider(source)
    app.dependency_overrides[get_xt_model] = lambda: active
    with TestClient(app) as client:
        yield client, source
    app.dependency_overrides.clear()
    get_xt_model.cache_clear()


def test_signed_totals_null_and_identity(client):
    client, _ = client
    result = client.get('/api/v1/matches/1/teams/10/xt/players')
    assert result.status_code == 200
    rows = result.json()['players']
    assert [row['player_id'] for row in rows] == [100, 101]  # same name, separate people
    p = rows[0]
    assert p['positive_xt'] == pytest.approx(.3)
    assert p['net_xt'] == pytest.approx(0)
    assert p['rated_action_count'] == 3
    assert p['rated_passes'] == 2 and p['rated_carries'] == 1
    assert p['action_count'] == 5
    assert rows[1]['positive_xt'] is None and rows[1]['net_xt'] is None


def test_action_schema_boundaries_and_missing_coordinates(client):
    client, _ = client
    result = client.get('/api/v1/matches/1/teams/10/xt/actions?limit=500')
    assert result.status_code == 200
    data = result.json()
    rows = data['actions']
    assert data['total'] == 6  # the shot is not a movement valuation
    assert [r['type'] for r in rows[:2]] == ['Pass', 'Carry']
    assert [r['xt'] for r in rows[:3]] == pytest.approx([.3, -.3, 0])
    assert rows[3]['xt'] is None and not rows[3]['successful']
    assert rows[4]['xt'] is None and rows[4]['end_x'] is None
    assert rows[5]['x'] is None and rows[5]['xt'] is None
    assert all(r['team_id'] == 10 for r in rows)
    assert [r['event_index'] for r in rows] == list(range(6))
    assert 'NaN' not in result.text
    page = client.get('/api/v1/matches/1/teams/10/xt/actions?limit=2&offset=2').json()
    assert [r['id'] for r in page['actions']] == ['zero', 'failed']
    assert page['total'] == 6
    assert client.get('/api/v1/matches/1/teams/10/xt/actions?player_id=101').json()['total'] == 1


def test_model_contract_and_no_training(client, monkeypatch):
    import src.expected_threat as xt
    monkeypatch.setattr(xt, 'fit', Mock(side_effect=AssertionError('HTTP must never train')))
    client, source = client
    data = client.get('/api/v1/xt/model').json()
    assert data['surface'] == [[.1, .4]]
    assert data['shot_counts'] == [[0, 2]]
    assert data['coverage']['shot_zones'] == 1
    assert data['experimental'] is True
    source.events.assert_not_called()
    assert client.get('/api/v1/matches/1/teams/10/xt/actions').status_code == 200


def test_shipped_model_is_sparse_and_unchanged():
    active = read_xt_model(MODEL_PATH)
    raw = MODEL_PATH.read_bytes()
    # Git may check text out as CRLF on Windows and LF on Linux. Verify the
    # frozen content separately from the API's intentional byte-level identity.
    assert hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest() == '8315bab1e55db6e03fe604c176e0a12253b66098dbb2a92d53379cc2a5a97ef6'
    assert active.info.model_id == hashlib.sha256(raw).hexdigest()
    assert (active.info.nx, active.info.ny) == (16, 12)
    assert active.info.coverage.shot_zones == 26
    assert len(active.info.coverage.train_ids) == 6
    assert len(active.info.coverage.held_out_ids) == 2


@pytest.mark.parametrize('newline', [b'\n', b'\r\n'])
def test_artifact_identity_matches_served_bytes_across_checkout_line_endings(tmp_path, newline):
    """Line endings change byte identity, never the frozen scoring surface."""
    raw = MODEL_PATH.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', newline)
    path = tmp_path / 'checkout.json'
    path.write_bytes(raw)
    active = read_xt_model(path)
    assert active.info.model_id == hashlib.sha256(raw).hexdigest()
    assert active.info.surface == read_xt_model(MODEL_PATH).info.surface


def test_artifact_cache_and_recovery(model_path, monkeypatch):
    import backend.api.xt_model as serving
    serving.get_xt_model.cache_clear()
    monkeypatch.setattr(serving, 'MODEL_PATH', model_path)
    first = serving.get_xt_model()
    assert serving.get_xt_model() is first
    serving.get_xt_model.cache_clear()
    original = model_path.read_bytes()
    model_path.unlink()
    with pytest.raises(Exception) as exc:
        serving.get_xt_model()
    assert exc.value.status_code == 503
    assert serving.get_xt_model.cache_info().currsize == 0
    model_path.write_bytes(original)
    assert serving.get_xt_model().info.model_id == first.info.model_id
    serving.get_xt_model.cache_clear()


@pytest.mark.parametrize('corruption', ['missing', 'json', 'surface', 'coordinates', 'coverage'])
def test_artifact_errors_are_safe_http_503(model_path, monkeypatch, corruption):
    import backend.api.xt_model as serving
    model = json.loads(model_path.read_text())
    if corruption == 'missing': model_path.unlink()
    elif corruption == 'json': model_path.write_text('{bad JSON')
    else:
        if corruption == 'surface': model['surface'] = [[float('nan'), .4]]
        if corruption == 'coordinates': model['metadata']['coordinate_system'] = 'unknown'
        if corruption == 'coverage': model['diagnostics']['shots'] = [-1, 2]
        model_path.write_text(json.dumps(model))
    monkeypatch.setattr(serving, 'MODEL_PATH', model_path)
    serving.get_xt_model.cache_clear()
    with TestClient(app) as client:
        response = client.get('/api/v1/xt/model')
    assert response.status_code == 503
    assert response.json() == {'detail': 'Experimental xT model unavailable'}
    assert str(model_path) not in response.text
    serving.get_xt_model.cache_clear()


@pytest.mark.parametrize('query', ['limit=0', 'limit=501', 'offset=-1', 'player_id=0'])
def test_xt_query_validation(client, query):
    client, _ = client
    assert client.get(f'/api/v1/matches/1/teams/10/xt/actions?{query}').status_code == 422


def test_provider_errors_and_unknown_team(client):
    client, source = client
    assert client.get('/api/v1/matches/1/teams/99/xt/players').status_code == 404
    source.events.side_effect = Timeout()
    assert client.get('/api/v1/matches/2/teams/10/xt/actions').status_code == 504


def test_summary_does_not_mutate_events(events, model_path):
    original = events.copy(deep=True)
    moves = valued_moves(events, read_xt_model(model_path).model)
    summary = player_xt_summary(moves)
    assert summary.iloc[0].net_xt == pytest.approx(0)
    pd.testing.assert_frame_equal(events, original)
