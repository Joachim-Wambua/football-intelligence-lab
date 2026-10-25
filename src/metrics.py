"""Passing filters and descriptive metrics; no predictive models."""

from math import isfinite
from numbers import Real

import pandas as pd


def select_passes(events: pd.DataFrame, team: str, player: str | None = None) -> pd.DataFrame:
    """Copy a team's passes and add completed, x, y, end_x and end_y.

    A missing pass_outcome means completion in StatsBomb. Invalid or absent
    coordinates become NaN; those passes still count in summary statistics.
    An absent outcome column means every pass has a missing outcome.
    """
    passes = events.loc[events["type"].eq("Pass") & events["team"].eq(team)].copy()
    if player is not None:
        passes = passes.loc[passes["player"].eq(player)].copy()
    outcomes = passes.get("pass_outcome", pd.Series(index=passes.index, dtype=object))
    passes["completed"] = outcomes.isna()
    for source, columns in (("location", ("x", "y")),
                            ("pass_end_location", ("end_x", "end_y"))):
        locations = passes.get(source, pd.Series(index=passes.index, dtype=object))
        for index, column in enumerate(columns):
            limit = 120 if index == 0 else 80
            passes[column] = locations.map(
                lambda value: _coordinate(value, index, limit)
            ).astype(float)
    return passes


def _coordinate(value: object, index: int, limit: int) -> float:
    """Extract a finite coordinate inside the StatsBomb pitch bounds."""
    if isinstance(value, (list, tuple)) and len(value) > index:
        coordinate = value[index]
        if isinstance(coordinate, Real) and isfinite(coordinate) and 0 <= coordinate <= limit:
            return float(coordinate)
    return float("nan")


def passing_summary(passes: pd.DataFrame) -> dict[str, int | float]:
    """Return attempts, completions and completion percentage (0 for no passes)."""
    attempted = len(passes)
    completed = int(passes["completed"].sum())
    return {"attempted": attempted, "completed": completed,
            "completion_pct": 100 * completed / attempted if attempted else 0.0}


def select_shots(events: pd.DataFrame, team: str) -> pd.DataFrame:
    """Prepare team shots; missing xG stays NaN rather than becoming zero."""
    shots = events.loc[events["type"].eq("Shot") & events["team"].eq(team)].copy()
    locations = shots.get("location", pd.Series(index=shots.index, dtype=object))
    for index, (column, limit) in enumerate((("x", 120), ("y", 80))):
        shots[column] = locations.map(lambda value: _coordinate(value, index, limit)).astype(float)
    shots["goal"] = shots.get(
        "shot_outcome", pd.Series(index=shots.index, dtype=object)
    ).eq("Goal")
    shots["xg"] = pd.to_numeric(shots.get(
        "shot_statsbomb_xg", pd.Series(index=shots.index, dtype=float)
    ), errors="coerce")
    shots["xg"] = shots["xg"].where(shots["xg"].between(0, 1))
    return shots


def player_statistics(events: pd.DataFrame, team: str) -> pd.DataFrame:
    """Aggregate event-observed players; no minutes or per-90 estimates.

    Counts passes, shots, shot goals, successful dribbles and interceptions.
    xG is the sum of available provider values (NaN when none are recorded).
    """
    team_events = events.loc[events["team"].eq(team)]
    players = team_events.get("player", pd.Series(dtype=object)).dropna().unique()
    rows = []
    for player in sorted(players):
        subset = team_events.loc[team_events["player"].eq(player)]
        rows.append({"Player": player, **descriptive_statistics(subset, team)})
    return pd.DataFrame(rows, columns=["Player", "Passes", "Completed passes",
        "Pass completion %", "Shots", "Goals", "xG", "Successful dribbles",
        "Successful interceptions"])


def descriptive_statistics(events: pd.DataFrame, team: str) -> dict:
    """Shared event counts for an already ID-filtered person or a team.

    Completion follows the StatsBomb omitted-outcome convention. xG sums
    available probabilities only; all unknown stays NaN, including no shots.
    Counts are observed events, not minutes, ratings or predicted outcomes.
    """
    events = events.loc[events.team.eq(team)]
    passing = passing_summary(select_passes(events, team))
    shots = select_shots(events, team)
    dribbles = events.get("dribble_outcome", pd.Series(index=events.index, dtype=object))
    interceptions = events.get("interception_outcome", pd.Series(index=events.index, dtype=object))
    return {"Passes": passing["attempted"], "Completed passes": passing["completed"],
        "Pass completion %": passing["completion_pct"], "Shots": len(shots), "Goals": int(shots.goal.sum()),
        "xG": shots.xg.sum(min_count=1),
        "Successful dribbles": int((events.type.eq("Dribble") & dribbles.eq("Complete")).sum()),
        "Successful interceptions": int((events.type.eq("Interception") & interceptions.isin(
            ["Won", "Success", "Success In Play", "Success Out"])).sum())}
