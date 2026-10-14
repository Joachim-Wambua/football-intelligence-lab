"""V1 shot, player and local dataset checks."""
import json

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from src.datasets import LocalDatasetSource
from src.metrics import player_statistics, select_passes, select_shots
from src.visualizations import shot_map


def test_player_statistics_and_shots():
    events = pd.DataFrame([
        {"type": "Pass", "team": "A", "player": "P"},
        {"type": "Pass", "team": "A", "player": "Q", "pass_outcome": "Out"},
        {"type": "Shot", "team": "A", "player": "P", "shot_outcome": "Goal", "shot_statsbomb_xg": .4, "location": [110, 40]},
        {"type": "Shot", "team": "A", "player": "P", "shot_outcome": "Saved", "location": None},
        {"type": "Dribble", "team": "A", "player": "P", "dribble_outcome": "Complete"},
        {"type": "Shot", "team": "B", "player": "P", "shot_outcome": "Goal"},
    ])
    assert len(select_passes(events, "A", "P")) == 1
    stats = player_statistics(events, "A").set_index("Player")
    assert stats.loc["P", "Shots"] == 2
    assert stats.loc["P", "Goals"] == 1
    assert stats.loc["P", "xG"] == pytest.approx(.4)
    assert stats.loc["P", "Successful dribbles"] == 1
    assert pd.isna(stats.loc["Q", "xG"])
    shots = select_shots(events, "A")
    assert shots.xg.isna().sum() == 1
    fig = shot_map(shots)
    try:
        fig.canvas.draw()
        assert sum(len(c.get_offsets()) for c in fig.axes[0].collections) == 1
    finally:
        plt.close(fig)


def test_empty_shots_and_statistics():
    events = pd.DataFrame(columns=["type", "team", "player"])
    assert player_statistics(events, "A").empty
    fig = shot_map(select_shots(events, "A"))
    try:
        fig.canvas.draw()
        assert any("No shots" in t.get_text() for t in fig.axes[0].texts)
    finally:
        plt.close(fig)


def test_local_bvb_source(tmp_path):
    (tmp_path / "events").mkdir()
    (tmp_path / "competitions.json").write_text(json.dumps([
        {"competition_id": 9, "season_id": 281, "competition_name": "Bundesliga", "season_name": "2023/24"}]))
    (tmp_path / "matches.json").write_text(json.dumps([
        {"competition_id": 9, "season_id": 281, "match_id": 7, "match_date": "2024-01-01", "home_team": "BVB", "away_team": "A"},
        {"competition_id": 9, "season_id": 282, "match_id": 8, "match_date": "2025-01-01", "home_team": "BVB", "away_team": "B"}]))
    (tmp_path / "events" / "7.json").write_text(json.dumps([
        {"type": "Pass", "team": "BVB", "player": "P", "location": [1, 2], "pass_end_location": [3, 4]}]))
    source = LocalDatasetSource(tmp_path)
    assert source.competitions().iloc[0].competition_id == 9
    assert source.matches(9, 281).match_id.tolist() == [7]
    assert select_passes(source.events(7), "BVB").iloc[0].end_x == 3
