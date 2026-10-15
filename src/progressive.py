"""Geometric passing progression, independent of plotting and Streamlit.

Goal centre is (120, 40). Metres-equivalent distances assume a configurable
105 x 68 m pitch; raw StatsBomb units are not metres. Classification uses an
inclusive absolute reduction in scaled distance, not pass length or x gain.
"""

from dataclasses import dataclass
from math import hypot, isfinite
from numbers import Real

import pandas as pd

from src.metrics import select_passes


@dataclass(frozen=True)
class ProgressionConfig:
    """Project-specific rule: at least 10 m-equivalent closer to goal.

    This is not a claim to implement a provider's progressive-pass definition.
    Dimensions describe an assumed pitch, not known match-specific dimensions.
    """

    threshold_m: float = 10.0
    pitch_length_m: float = 105.0
    pitch_width_m: float = 68.0

    def __post_init__(self):
        for value in (self.threshold_m, self.pitch_length_m, self.pitch_width_m):
            if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value) or value <= 0:
                raise ValueError("Threshold and pitch dimensions must be finite positive numbers.")


def distance_to_goal(location: object, config: ProgressionConfig | None = None) -> float:
    """Euclidean distance to (120, 40); NaN for malformed coordinates.

    With no config return StatsBomb units. With config scale x by length/120
    and y by width/80 before taking the norm, yielding metres-equivalent.
    Requires exactly two finite numeric coordinates in the 120 x 80 bounds.
    """
    if not isinstance(location, (list, tuple)) or len(location) != 2:
        return float("nan")
    x, y = location
    if any(isinstance(v, bool) or not isinstance(v, Real) or not isfinite(v) for v in (x, y)):
        return float("nan")
    if not (0 <= x <= 120 and 0 <= y <= 80):
        return float("nan")
    sx, sy = (1.0, 1.0) if config is None else (config.pitch_length_m / 120, config.pitch_width_m / 80)
    return hypot((120 - x) * sx, (40 - y) * sy)


def progressive_passes(events: pd.DataFrame, team: str,
                       config: ProgressionConfig = ProgressionConfig()) -> pd.DataFrame:
    """Return team passes with signed progression and separate success flags.

    An invalid endpoint has NaN distance; differences are NaN if either is invalid. Such
    passes have valid_geometry=False and both progressive flags False, but
    remain in attempt totals. A geometrically progressive incomplete pass is
    progressive=True, completed_progressive=False. Inputs are never mutated.
    """
    passes = select_passes(events, team)
    for prefix, column in (("start", "location"), ("end", "pass_end_location")):
        locations = passes.get(column, pd.Series(index=passes.index, dtype=object))
        passes[f"{prefix}_distance_sb"] = locations.map(distance_to_goal).astype(float)
        passes[f"{prefix}_distance_m"] = locations.map(lambda p: distance_to_goal(p, config)).astype(float)
    passes["valid_geometry"] = passes[["start_distance_sb", "end_distance_sb"]].notna().all(axis=1)
    passes["progression_sb"] = passes.start_distance_sb - passes.end_distance_sb
    passes["progression_m"] = passes.start_distance_m - passes.end_distance_m
    passes["progressive"] = passes.valid_geometry & passes.progression_m.ge(config.threshold_m)
    passes["completed_progressive"] = passes.progressive & passes.completed
    return passes


def player_progression_comparison(passes: pd.DataFrame) -> pd.DataFrame:
    """Compare named passers from progressive_passes output.

    Rate denominator is all attempted passes, including unclassifiable ones;
    valid-coordinate coverage is reported separately. Net progression includes
    backward passes and both outcomes; sum is NaN when no geometry is valid.
    Players with no passes and unnamed events do not appear. No per-90 inference.
    """
    columns = ["Player", "Passes", "Valid geometry", "Progressive attempts",
               "Completed progressive", "Progressive %", "Net progression (m equivalent)"]
    if "player" not in passes:
        return pd.DataFrame(columns=columns)
    rows = []
    for player, group in passes.dropna(subset=["player"]).groupby("player", sort=True):
        count = int(group.progressive.sum())
        rows.append([player, len(group), int(group.valid_geometry.sum()), count,
                     int(group.completed_progressive.sum()), 100 * count / len(group),
                     group.progression_m.sum(min_count=1)])
    return pd.DataFrame(rows, columns=columns)
