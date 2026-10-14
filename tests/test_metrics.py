"""Deterministic passing checks using small synthetic event tables."""

import pandas as pd
import pytest

from src.metrics import passing_summary, select_passes


@pytest.fixture
def events():
    return pd.DataFrame([
        {"type": "Pass", "team": "A", "location": [10, 20],
         "pass_end_location": [30, 40], "pass_outcome": None},
        {"type": "Pass", "team": "A", "location": None,
         "pass_end_location": [121, 40], "pass_outcome": "Incomplete"},
        {"type": "Shot", "team": "A"},
        {"type": "Pass", "team": "B", "pass_outcome": "Out"},
    ])


def test_filter_summary_and_missing_coordinates(events):
    passes = select_passes(events, "A")
    assert len(passes) == 2
    assert passes.iloc[0]["end_x"] == 30
    assert pd.isna(passes.iloc[1]["x"])
    assert pd.isna(passes.iloc[1]["end_x"])
    assert passing_summary(passes) == {
        "attempted": 2, "completed": 1, "completion_pct": 50.0}
    assert "completed" not in events.columns


def test_no_passes(events):
    passes = select_passes(events, "Unknown")
    assert passing_summary(passes) == {
        "attempted": 0, "completed": 0, "completion_pct": 0.0}


def test_all_completed_without_outcome_column():
    events = pd.DataFrame([{"type": "Pass", "team": "A"}])
    assert passing_summary(select_passes(events, "A"))["completion_pct"] == 100


@pytest.mark.parametrize("location", [[float("inf"), 2], [1], "bad", [-1, 3], [1, 81]])
def test_invalid_locations_are_not_drawable(location):
    events = pd.DataFrame([{"type": "Pass", "team": "A", "location": location}])
    passes = select_passes(events, "A")
    assert passes[["x", "y"]].isna().any(axis=None)
