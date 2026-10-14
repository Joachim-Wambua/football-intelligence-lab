"""Matplotlib figures for prepared StatsBomb passing data."""

import pandas as pd
from matplotlib.figure import Figure
from mplsoccer import Pitch


def passing_map(passes: pd.DataFrame, title: str = "Passing map") -> Figure:
    """Draw valid pass trajectories on a 120 x 80 StatsBomb pitch.

    Accepts select_passes output. Missing coordinates are omitted from the
    figure only. Returns a figure; callers own its rendering and cleanup.
    """
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#f5f7f2", line_color="#516350")
    fig, ax = pitch.draw(figsize=(10, 7))
    drawable = passes.dropna(subset=["x", "y", "end_x", "end_y"])
    for completed, color, label in ((True, "#167d9a", "Completed"),
                                     (False, "#c65d28", "Unsuccessful")):
        subset = drawable.loc[drawable["completed"].eq(completed)]
        pitch.arrows(subset["x"], subset["y"], subset["end_x"], subset["end_y"],
                     ax=ax, color=color, alpha=0.65, width=1.5, label=label)
    ax.legend(loc="upper left")
    ax.set_title(title)
    if drawable.empty:
        ax.text(60, 40, "No passes with valid coordinates", ha="center")
    return fig


def shot_map(shots: pd.DataFrame, title: str = "Team shot map") -> Figure:
    """Plot goals and other shots; marker area scales with known provider xG."""
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#f5f7f2", line_color="#516350")
    fig, ax = pitch.draw(figsize=(10, 7))
    drawable = shots.dropna(subset=["x", "y"])
    for goal, color, marker, label in ((True, "#167d9a", "*", "Goal"),
                                       (False, "#c65d28", "o", "Other shot")):
        subset = drawable.loc[drawable["goal"].eq(goal)]
        pitch.scatter(subset["x"], subset["y"], s=60 + 500 * subset["xg"].fillna(0),
                      color=color, marker=marker, alpha=0.8, label=label, ax=ax)
    ax.legend(loc="upper left")
    ax.set_title(title)
    if drawable.empty:
        ax.text(60, 40, "No shots with valid coordinates", ha="center")
    return fig
