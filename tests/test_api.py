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
