"""Figures consuming prepared progression tables; no UI dependencies."""

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from mplsoccer import Pitch
import pandas as pd


def progressive_map(passes: pd.DataFrame, title: str = "Progressive passes") -> Figure:
    """Draw qualifying completed and incomplete passes; caller closes figure."""
    pitch = Pitch(pitch_type="statsbomb")
    fig, ax = pitch.draw(figsize=(10, 7))
    selected = passes.loc[passes.progressive & passes.valid_geometry]
    for completed, color, label in ((True, "#167d9a", "Completed progressive"),
                                     (False, "#c65d28", "Incomplete progressive")):
        subset = selected.loc[selected.completed.eq(completed)]
        pitch.arrows(subset.x, subset.y, subset.end_x, subset.end_y,
                     ax=ax, color=color, label=label, width=2)
    ax.legend(loc="upper left")
    ax.set_title(title)
    if selected.empty:
        ax.text(60, 40, "No qualifying progressive passes", ha="center")
    return fig


def progression_comparison_chart(comparison: pd.DataFrame) -> Figure:
    """Stack completed and incomplete progressive counts for named passers."""
    fig, ax = plt.subplots(figsize=(10, max(3, len(comparison) * .35)))
    if comparison.empty:
        ax.text(.5, .5, "No named passers available", transform=ax.transAxes, ha="center")
    else:
        completed = comparison["Completed progressive"]
        incomplete = comparison["Progressive attempts"] - completed
        ax.barh(comparison.Player, completed, label="Completed", color="#167d9a")
        ax.barh(comparison.Player, incomplete, left=completed, label="Incomplete", color="#c65d28")
        ax.legend()
    ax.set_xlabel("Progressive pass attempts")
    ax.set_title("Player progression comparison")
    fig.tight_layout()
    return fig
