"""Render real figures on a noninteractive backend."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.metrics import select_passes
from src.visualizations import passing_map


def test_map_with_valid_and_missing_coordinates(tmp_path):
    events = pd.DataFrame([
        {"type": "Pass", "team": "A", "location": [10, 20],
         "pass_end_location": [50, 30]},
        {"type": "Pass", "team": "A", "location": None},
    ])
    fig = passing_map(select_passes(events, "A"), "Team A")
    try:
        output = tmp_path / "map.png"
        fig.savefig(output)
        assert output.stat().st_size > 0
        assert fig.axes[0].get_title() == "Team A"
    finally:
        plt.close(fig)


def test_empty_map():
    events = pd.DataFrame(columns=["type", "team"])
    fig = passing_map(select_passes(events, "A"))
    try:
        fig.canvas.draw()
        assert any("No passes" in text.get_text() for text in fig.axes[0].texts)
    finally:
        plt.close(fig)
