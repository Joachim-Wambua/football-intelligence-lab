"""Versioned read-only xT contracts; xT values are model estimates, never per-90."""

from datetime import datetime
from typing import Literal

from backend.api.schemas import Contract


class XTCoverage(Contract):
    train_ids: list[int]
    held_out_ids: list[int]
    published_matches: int
    locally_eligible_matches: int
    training_shots: int
    training_goals: int
    shot_zones: int
    total_zones: int


class XTModelInfo(Contract):
    model_id: str
    artifact_version: Literal[1]
    nx: int
    ny: int
    surface: list[list[float]]
    shot_counts: list[list[int]]
    coordinate_system: Literal['StatsBomb 120x80 attacking right']
    provider: str
    provenance: str
    trained_at: datetime
    competition_id: int
    season_id: int
    fallback: str
    tolerance: float
    iterations: int
    final_residual: float
    manifest_sha256: str
    event_sha256: dict[str, str]
    coverage: XTCoverage
    experimental: Literal[True] = True


class XTPlayer(Contract):
    player_id: int
    player: str
    action_count: int
    rated_action_count: int
    rated_passes: int
    rated_carries: int
    positive_xt: float | None
    net_xt: float | None


class XTPlayers(Contract):
    model_id: str
    match_id: int
    team_id: int
    players: list[XTPlayer]


class XTAction(Contract):
    event_index: int
    id: str | None = None
    type: Literal['Pass', 'Carry']
    player_id: int | None
    player: str | None
    team_id: int
    period: int | None = None
    minute: int | None = None
    second: int | None = None
    successful: bool
    x: float | None
    y: float | None
    end_x: float | None
    end_y: float | None
    xt: float | None


class XTActions(Contract):
    model_id: str
    match_id: int
    team_id: int
    total: int
    offset: int
    limit: int
    actions: list[XTAction]
