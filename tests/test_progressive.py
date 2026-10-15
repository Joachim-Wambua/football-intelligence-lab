"""Analytical geometry and completion semantics, without network or UI."""

from math import hypot, isnan

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from src.progressive import (ProgressionConfig, distance_to_goal, progressive_passes,
                             player_progression_comparison)
from src.progressive_visualizations import progressive_map, progression_comparison_chart


def event(start, end, outcome=None, player="P"):
    return {"type": "Pass", "team": "A", "player": player,
            "location": start, "pass_end_location": end, "pass_outcome": outcome}


def test_distance_and_anisotropic_scaling():
    assert distance_to_goal([120, 40]) == 0
    assert distance_to_goal([0, 0]) == pytest.approx(hypot(120, 40))
    assert distance_to_goal([0, 0], ProgressionConfig()) == pytest.approx(hypot(105, 34))
    assert distance_to_goal([120, 80], ProgressionConfig(pitch_width_m=80)) == 40


@pytest.mark.parametrize("start,end,expected,qualifies", [
    ([40, 40], [60, 40], 17.5, True),  # forward
    ([60, 40], [40, 40], -17.5, False),  # backward
    ([60, 20], [60, 60], 0, False),  # lateral, symmetric about centre
    ([120, 0], [120, 40], 34, True),  # lateral toward goal centre
    ([120, 40], [120, 0], -34, False),
    ([0, 40], [120, 40], 105, True),
    ([50, 40], [50, 40], 0, False),
])
def test_signed_progression(start, end, expected, qualifies):
    result = progressive_passes(pd.DataFrame([event(start, end)]), "A").iloc[0]
    assert result.progression_m == pytest.approx(expected)
    assert bool(result.progressive) is qualifies


def test_completion_threshold_and_copy():
    events = pd.DataFrame([event([40, 40], [60, 40]),
                           event([40, 40], [60, 40], "Incomplete")])
    original = events.copy(deep=True)
    result = progressive_passes(events, "A", ProgressionConfig(threshold_m=17.5))
    assert result.progressive.tolist() == [True, True]
    assert result.completed_progressive.tolist() == [True, False]
    assert not progressive_passes(events, "A", ProgressionConfig(threshold_m=17.51)).progressive.any()
    pd.testing.assert_frame_equal(events, original)
    table = player_progression_comparison(result).iloc[0]
    assert table["Passes"] == 2
    assert table["Progressive attempts"] == 2
    assert table["Completed progressive"] == 1


@pytest.mark.parametrize("location", [None, [], [1], [1, 2, 3], "bad", [True, 4],
    ["1", 2], [float("nan"), 1], [float("inf"), 2], [-1, 40], [121, 40], [30, 81]])
def test_malformed_passes(location):
    assert isnan(distance_to_goal(location))
    events = pd.DataFrame([event(location, [100, 40]), event([10, 40], location)])
    result = progressive_passes(events, "A")
    assert not result.valid_geometry.any()
    assert result.progression_m.isna().all()
    assert not result.progressive.any()
    assert not result.completed_progressive.any()
    table = player_progression_comparison(result).iloc[0]
    assert table["Passes"] == 2
    assert table["Valid geometry"] == 0
    assert pd.isna(table["Net progression (m equivalent)"])


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, "10"])
@pytest.mark.parametrize("field", ["threshold_m", "pitch_length_m", "pitch_width_m"])
def test_config_validation(field, value):
    with pytest.raises(ValueError):
        ProgressionConfig(**{field: value})


def test_empty_and_populated_figures():
    events = pd.DataFrame([event([40, 40], [60, 40]),
                           event([40, 40], [60, 40], "Out", "Q"),
                           event(None, None, player="R")])
    for team in ["A", "Missing"]:
        passes = progressive_passes(events, team)
        table = player_progression_comparison(passes)
        figures = [progressive_map(passes), progression_comparison_chart(table)]
        try:
            for fig in figures:
                fig.canvas.draw()
        finally:
            for fig in figures:
                plt.close(fig)


def test_team_filter_and_coverage_denominator():
    events = pd.DataFrame([event([40, 40], [60, 40]), event(None, None),
                           {**event([40, 40], [60, 40]), "team": "B"}])
    passes = progressive_passes(events, "A")
    row = player_progression_comparison(passes).iloc[0]
    assert row["Passes"] == 2
    assert row["Valid geometry"] == 1
    assert row["Progressive %"] == 50
