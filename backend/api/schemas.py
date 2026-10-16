"""Explicit JSON contracts; unavailable numeric measurements are null."""

from typing import Literal
from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)


class Health(Contract):
    status: Literal["ok"] = "ok"


class Error(Contract):
    detail: str


class Competition(Contract):
    competition_id: int
    season_id: int
    competition_name: str
    season_name: str
    country_name: str | None = None
    competition_gender: str | None = None


class Match(Contract):
    match_id: int
    match_date: str
    home_team: str
    away_team: str
    home_score: int | None = None
    away_score: int | None = None


class PassingSummary(Contract):
    attempted: int
    completed: int
    completion_pct: float


class TeamSummary(Contract):
    team_id: int
    team: str
    passing: PassingSummary
    shots: int
    shot_goals: int
    recorded_xg: float | None
    shots_with_xg: int


class MatchSummary(Contract):
    match_id: int
    event_count: int
    teams: list[TeamSummary]


class PlayerStatistics(Contract):
    player_id: int
    player: str
    passes: int
    completed_passes: int
    pass_completion_pct: float
    shots: int
    goals: int
    xg: float | None
    successful_dribbles: int
    successful_interceptions: int


class Pass(Contract):
    """Recorded attempt; null progression and false flags mean unclassifiable geometry.

    Progressive is geometric and may be unsuccessful. Completed progressive
    requires both the progressive and completed flags.
    """

    id: str | None = None
    minute: int | None = None
    second: int | None = None
    period: int | None = None
    completed: bool
    x: float | None
    y: float | None
    end_x: float | None
    end_y: float | None
    valid_geometry: bool
    start_distance_sb: float | None
    end_distance_sb: float | None
    start_distance_m: float | None
    end_distance_m: float | None
    progression_sb: float | None
    progression_m: float | None
    progressive: bool
    completed_progressive: bool


class ProgressionDefinition(Contract):
    """The precise assumptions used to classify the returned records."""

    threshold_m: float
    pitch_length_m: float
    pitch_width_m: float
    goal_x: int = 120
    goal_y: int = 40
    comparison: Literal["greater_than_or_equal"] = "greater_than_or_equal"


class PlayerProgression(Contract):
    """Named passer totals; net progression is signed, across both outcomes."""

    rank: int
    player_id: int
    player: str
    passes: int
    valid_geometry: int
    progressive_attempts: int
    completed_progressive: int
    progressive_pct: float
    net_progression_m: float | None


class TeamProgression(Contract):
    match_id: int
    team_id: int
    definition: ProgressionDefinition
    players: list[PlayerProgression]
