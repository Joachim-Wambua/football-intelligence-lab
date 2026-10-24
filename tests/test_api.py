"""HTTP contracts, cache behavior and upstream failures, using no live data."""

import json
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from requests import HTTPError, Response, Timeout

from backend.api.main import app
from backend.api.provider import CachedProvider, get_provider
from backend.api.serialization import records


@pytest.fixture
def source():
    source = Mock()
    source.competitions.return_value = pd.DataFrame([
        {"competition_id": 9, "season_id": 281, "competition_name": "Bundesliga", "season_name": "2023/24"}])
    source.matches.return_value = pd.DataFrame([
        {"match_id": 1, "match_date": "2024-01-01", "home_team": "A", "away_team": "B", "home_score": 1, "away_score": 0}])
    source.events.return_value = pd.DataFrame([
        {"id": "pass-1", "type": "Pass", "team": "A", "team_id": 10, "player": "P", "player_id": 100,
         "location": [10, 20], "pass_end_location": [40, 30], "minute": 1},
        {"id": "pass-2", "type": "Pass", "team": "A", "team_id": 10, "player": "P", "player_id": 100,
         "location": [np.inf, 20], "pass_end_location": None, "pass_outcome": "Incomplete"},
        {"type": "Shot", "team": "A", "team_id": 10, "player": "Q", "player_id": 101,
         "location": [110, 40], "shot_outcome": "Goal", "shot_statsbomb_xg": .3},
        {"type": "Shot", "team": "B", "team_id": 20, "player": "R", "player_id": 200,
         "location": [100, 40], "shot_statsbomb_xg": np.inf},
    ])
    return source


@pytest.fixture
def client(source):
    provider = CachedProvider(source)
    app.dependency_overrides[get_provider] = lambda: provider
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_health_and_openapi(client, source):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    source.competitions.assert_not_called()
    assert "PlayerStatistics" in client.get("/openapi.json").json()["components"]["schemas"]


def test_competitions_and_matches(client, source):
    assert client.get("/api/v1/competitions").json()[0]["competition_id"] == 9
    assert client.get("/api/v1/matches").json()[0]["match_id"] == 1
    assert client.get("/api/v1/matches?competition_id=999&season_id=281").status_code == 404
    client.get("/api/v1/matches")
    source.matches.assert_called_once_with(9, 281)
    source.competitions.assert_called_once()


def test_summary_and_shared_statistics(client):
    data = client.get("/api/v1/matches/1/summary").json()
    assert data["event_count"] == 4
    assert data["teams"][0]["passing"] == {"attempted": 2, "completed": 1, "completion_pct": 50}
    assert data["teams"][0]["shot_goals"] == 1
    assert data["teams"][1]["recorded_xg"] is None
    response = client.get("/api/v1/matches/1/teams/10/players")
    assert response.status_code == 200
    players = response.json()
    assert players[0]["player_id"] == 100
    assert players[0]["passes"] == 2
    assert players[0]["xg"] is None
    assert players[1]["goals"] == 1


def test_passes_json_and_no_passes(client):
    response = client.get("/api/v1/matches/1/players/100/passes")
    assert response.status_code == 200
    passes = response.json()
    assert passes[0]["completed"] is True
    assert passes[1]["completed"] is False
    assert passes[1]["x"] is None
    assert passes[1]["end_x"] is None
    assert "NaN" not in response.text and "Infinity" not in response.text
    assert client.get("/api/v1/matches/1/players/101/passes").json() == []


@pytest.mark.parametrize("path", ["/matches/0/summary", "/matches/bad/summary",
    "/matches/-1/summary", "/matches/1/teams/0/players", "/matches/1/players/-1/passes",
    "/matches?competition_id=0", "/matches?season_id=bad"])
def test_invalid_ids(client, path):
    assert client.get("/api/v1" + path).status_code == 422


@pytest.mark.parametrize("path", ["/matches/1/teams/999/players", "/matches/1/players/999/passes"])
def test_unknown_members(client, path):
    assert client.get("/api/v1" + path).status_code == 404


@pytest.mark.parametrize("failure,status", [(Timeout("secret"), 504), (ConnectionError("secret"), 502)])
def test_provider_failure_and_retry(client, source, failure, status):
    source.events.side_effect = failure
    response = client.get("/api/v1/matches/1/summary")
    assert response.status_code == status
    assert "secret" not in response.text
    client.get("/api/v1/matches/1/summary")
    assert source.events.call_count == 2


@pytest.mark.parametrize("upstream,status", [(404, 404), (429, 502), (500, 502)])
def test_upstream_http_errors(client, source, upstream, status):
    response = Response()
    response.status_code = upstream
    source.events.side_effect = HTTPError(response=response)
    assert client.get("/api/v1/matches/1/summary").status_code == status


def test_empty_and_malformed_data(client, source):
    source.events.return_value = pd.DataFrame()
    assert client.get("/api/v1/matches/999/summary").status_code == 404
    source.matches.return_value = pd.DataFrame()
    assert client.get("/api/v1/matches").json() == []
    source.competitions.return_value = pd.DataFrame([{"competition_id": 1}])
    # Different match bypasses the event-cache entry used above.
    source.events.return_value = pd.DataFrame([{"bad_column": 1}])
    assert client.get("/api/v1/matches/2/summary").status_code == 502


def test_invalid_response_contract(client, source):
    source.competitions.return_value = pd.DataFrame([{"competition_id": 9, "season_id": 281}])
    assert client.get("/api/v1/competitions").status_code == 502


def test_cors(client):
    headers = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"}
    allowed = client.options("/api/v1/competitions", headers=headers)
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    for origin in ["https://example.com", "http://localhost:3001", "http://127.0.0.1:3000"]:
        denied = client.options("/api/v1/competitions", headers={**headers, "Origin": origin})
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers
    assert client.options("/api/v1/competitions", headers={**headers, "Access-Control-Request-Method": "POST"}).status_code == 400


def test_cache_expiry_eviction_and_frame_isolation(source):
    now = [0]
    provider = CachedProvider(source, ttl=10, maxsize=2, timer=lambda: now[0])
    first = provider.events(1)
    first.loc[0, "team"] = "Changed"
    assert provider.events(1).loc[0, "team"] == "A"
    assert source.events.call_count == 1
    now[0] = 11
    provider.events(1)
    assert source.events.call_count == 2
    provider.events(2)
    provider.events(3)
    assert len(provider.cache) == 2
    provider.events(1)
    assert source.events.call_count == 5


def test_json_safe_nested_records():
    frame = pd.DataFrame([{"a": pd.NA, "b": np.inf, "c": -np.inf,
                           "d": [np.nan, np.int64(1)], "date": pd.Timestamp("2024-01-01")}])
    converted = records(frame)
    assert converted[0]["a"] is None
    assert converted[0]["b"] is None
    assert converted[0]["c"] is None
    assert converted[0]["d"] == [None, 1]
    json.dumps(converted, allow_nan=False)


@pytest.fixture
def progression_events(source):
    """Centreline examples with exact scaled differences; all belong to team A."""
    base = {"type": "Pass", "team": "A", "team_id": 10, "player": "Same name", "player_id": 100}
    source.events.return_value = pd.DataFrame([
        {**base, "location": [40, 40], "pass_end_location": [60, 40]},  # +17.5m
        {**base, "location": [40, 40], "pass_end_location": [60, 40], "pass_outcome": "Incomplete"},
        {**base, "location": [60, 40], "pass_end_location": [40, 40]},  # -17.5m
        {**base, "location": [60, 20], "pass_end_location": [60, 60]},  # lateral 0
        {**base, "location": [1, 2, 3], "pass_end_location": [60, 40]},  # malformed
        {**base, "player_id": 101, "location": [40, 40], "pass_end_location": [80, 40]},
        {**base, "player_id": 102, "player": "Unknown geometry", "location": None},
        {**base, "player_id": 103, "player": "No passes", "type": "Shot", "location": [100, 40]},
    ])
    return source.events.return_value


def test_progressive_flags_and_threshold(client, progression_events):
    path = "/api/v1/matches/1/players/100/passes"
    response = client.get(path + "?threshold_m=17.5")
    assert response.status_code == 200
    passes = response.json()
    assert [p["progressive"] for p in passes] == [True, True, False, False, False]
    assert [p["completed_progressive"] for p in passes] == [True, False, False, False, False]
    assert [p["progression_m"] for p in passes[:4]] == [17.5, 17.5, -17.5, 0]
    assert passes[0]["progression_sb"] == 20
    assert passes[4]["valid_geometry"] is False
    assert passes[4]["progression_m"] is None
    assert not any(p["progressive"] for p in client.get(path + "?threshold_m=17.5001").json())
    assert client.get("/api/v1/matches/1/players/103/passes").json() == []


def test_progressive_rankings_and_identity(client, progression_events, source):
    path = "/api/v1/matches/1/teams/10/progressive-passing"
    response = client.get(path)
    assert response.status_code == 200
    data = response.json()
    assert data["definition"] == {"threshold_m": 10, "pitch_length_m": 105, "pitch_width_m": 68,
        "goal_x": 120, "goal_y": 40, "comparison": "greater_than_or_equal"}
    rows = data["players"]
    assert [p["rank"] for p in rows] == [1, 2, 3]
    assert [p["player_id"] for p in rows] == [100, 101, 102]  # same name, distinct IDs
    assert rows[0]["passes"] == 5
    assert rows[0]["valid_geometry"] == 4
    assert rows[0]["progressive_attempts"] == 2
    assert rows[0]["completed_progressive"] == 1
    assert rows[0]["progressive_pct"] == 40
    assert rows[0]["net_progression_m"] == 17.5
    assert rows[2]["net_progression_m"] is None
    high = client.get(path + "?threshold_m=20").json()
    assert high["players"][0]["player_id"] == 101
    assert high["definition"]["threshold_m"] == 20
    source.events.assert_called_once_with(1)  # raw events reused across thresholds


@pytest.mark.parametrize("threshold", ["0", "-1", "nan", "inf", "-inf", "bad"])
@pytest.mark.parametrize("path", ["/matches/1/teams/10/progressive-passing", "/matches/1/players/100/passes"])
def test_invalid_progression_threshold(client, path, threshold):
    assert client.get(f"/api/v1{path}?threshold_m={threshold}").status_code == 422


def test_progressive_endpoint_errors(client, source):
    assert client.get("/api/v1/matches/1/teams/999/progressive-passing").status_code == 404
    assert client.get("/api/v1/matches/0/teams/10/progressive-passing").status_code == 422
    source.events.side_effect = Timeout()
    assert client.get("/api/v1/matches/2/teams/10/progressive-passing").status_code == 504


def test_progressive_team_with_no_passers(client, source):
    source.events.return_value = source.events.return_value.loc[source.events.return_value.type.eq("Shot")]
    response = client.get("/api/v1/matches/1/teams/10/progressive-passing")
    assert response.status_code == 200
    assert response.json()["players"] == []


def test_shot_events_and_insights(client):
    response = client.get('/api/v1/matches/1/shots')
    assert response.status_code == 200
    shots = response.json()
    assert len(shots) == 2
    assert shots[0]['match_id'] == 1
    assert shots[0]['player_id'] == 101
    assert shots[0]['goal'] is True
    assert shots[0]['xg'] == .3
    assert shots[0]['period'] is None
    assert shots[1]['xg'] is None
    assert len(client.get('/api/v1/matches/1/shots?team_id=10').json()) == 1
    assert client.get('/api/v1/matches/1/shots?team_id=999').status_code == 404
    assert client.get('/api/v1/matches/0/shots').status_code == 422
    assert client.get('/api/v1/matches/1/shots?team_id=-1').status_code == 422
    data = client.get('/api/v1/matches/1/teams/10/insights')
    assert data.status_code == 200, data.text
    observations = {row['metric']: row for row in data.json()['observations']}
    assert observations['shots']['value'] == 1
    assert observations['xg_coverage']['denominator'] == 1
    assert observations['recorded_xg']['value'] == .3
    assert all(row['definition'] for row in observations.values())


def test_shot_missing_geometry_empty_and_model_failure(client, source, monkeypatch):
    from fastapi import HTTPException
    from backend.api import workspace
    def unavailable():
        raise HTTPException(503, 'Unavailable')
    monkeypatch.setattr(workspace, 'get_xt_model', unavailable)
    source.events.return_value.loc[2, 'location'] = None
    source.events.return_value.loc[2, 'shot_statsbomb_xg'] = -1
    shot = client.get('/api/v1/matches/1/shots?team_id=10').json()[0]
    assert shot['x'] is None and shot['y'] is None and shot['xg'] is None
    data = client.get('/api/v1/matches/1/teams/10/insights').json()
    assert data['xt_status'] == 'unavailable'
    assert data['observations'][2]['value'] is None
    source.events.return_value = source.events.return_value.loc[source.events.return_value.type.eq('Pass')]
    assert client.get('/api/v1/matches/2/shots').json() == []
    data = client.get('/api/v1/matches/2/teams/10/insights').json()
    assert data['observations'][1]['value'] == 0
    assert data['observations'][1]['denominator'] == 0

def test_shot_probability_and_pitch_boundaries(client, source):
    """Zero xG is measured, unlike missing xG; pitch edges remain drawable."""
    base = {'type': 'Shot', 'team': 'A', 'team_id': 10, 'player_id': None}
    source.events.return_value = pd.DataFrame([
        {**base, 'location': [0, 0], 'shot_statsbomb_xg': 0, 'period': 5},
        {**base, 'location': [120, 80], 'shot_statsbomb_xg': 1},
        {**base, 'location': [121, 40], 'shot_statsbomb_xg': 1.1},
        {**base, 'location': None, 'shot_statsbomb_xg': None}])
    shots = client.get('/api/v1/matches/1/shots').json()
    assert [(row['x'], row['y']) for row in shots[:2]] == [(0, 0), (120, 80)]
    assert [row['xg'] for row in shots] == [0, 1, None, None]
    assert shots[0]['period'] == 5
    assert shots[0]['player_id'] is None
    assert shots[2]['x'] is None


def test_insight_progressive_leader_matches_existing_rankings(client, progression_events):
    ranking = client.get('/api/v1/matches/1/teams/10/progressive-passing').json()
    evidence = client.get('/api/v1/matches/1/teams/10/insights').json()
    leader = next(row for row in evidence['observations'] if row['metric'] == 'completed_progressive_leader')
    assert leader['player_id'] == ranking['players'][0]['player_id'] == 100
    assert leader['value'] == 1
    assert leader['denominator'] == 5
