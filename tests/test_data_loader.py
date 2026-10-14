"""Verify provider calls without downloading data."""

import pandas as pd

from src import data_loader


def test_default_competition_and_chronological_order(monkeypatch):
    def matches(**kwargs):
        assert kwargs == {"competition_id": 9, "season_id": 281}
        return pd.DataFrame({"match_id": [2, 1],
                             "match_date": ["2024-01-02", "2024-01-01"]})
    monkeypatch.setattr(data_loader.sb, "matches", matches)
    assert data_loader.load_matches()["match_id"].tolist() == [1, 2]


def test_event_request(monkeypatch):
    expected = pd.DataFrame({"type": ["Pass"]})
    def events(**kwargs):
        assert kwargs == {"match_id": 123, "split": False, "flatten_attrs": True}
        return expected
    monkeypatch.setattr(data_loader.sb, "events", events)
    assert data_loader.load_events(123) is expected
