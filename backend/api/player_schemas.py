"""Explicit player-foundation contracts; null is different from a measured zero."""
from typing import Literal
from pydantic import Field
from backend.api.schemas import Contract


class PlayerContributionStatistics(Contract):
    passes: int = Field(ge=0)
    completed_passes: int = Field(ge=0)
    completed_progressive_passes: int = Field(ge=0)
    progressive_valid_geometry: int = Field(ge=0)
    shots: int = Field(ge=0)
    goals: int = Field(ge=0)
    shots_with_xg: int = Field(ge=0)
    xg: float | None
    successful_dribbles: int = Field(ge=0)
    successful_interceptions: int = Field(ge=0)
    xt_positive: float | None
    xt_net: float | None
    xt_rated_actions: int = Field(ge=0)
    xt_attempted_actions: int = Field(ge=0)


class PlayerRates(Contract):
    """Matched-exposure per90 values; individual unknown rates stay null."""
    passes: float | None
    completed_passes: float | None
    completed_progressive_passes: float | None
    shots: float | None
    goals: float | None
    xg: float | None
    successful_dribbles: float | None
    successful_interceptions: float | None
    xt_positive: float | None
    xt_net: float | None


class PositionSpell(Contract):
    """Provider position history, without estimating time in that role."""
    position_id: int | None = Field(default=None, ge=0)
    position: str | None = None
    from_time: str | None = Field(default=None, alias="from")
    to_time: str | None = Field(default=None, alias="to")
    from_period: int | None = Field(default=None, ge=1, le=5)
    to_period: int | None = Field(default=None, ge=1, le=5)
    start_reason: str | None = None
    end_reason: str | None = None


class ComparisonEvidence(Contract):
    """Covered totals plus Python-qualified chart/rate values, in natural units."""
    label: str
    kind: Literal['observed', 'geometry', 'provider_estimate', 'experimental_estimate']
    definition: str
    total: float | None
    per90: float | None
    chart_total: float | None
    status: Literal['complete', 'covered_shots_only', 'rated_moves_only', 'geometry_partial', 'partial_sample', 'unavailable']
    coverage_count: int | None = Field(ge=0)
    coverage_total: int | None = Field(ge=0)
    note: str


class PlayerAggregate(Contract):
    appearances: int = Field(ge=0)
    unknown_appearances: int = Field(ge=0)
    minutes: float | None = Field(ge=0)
    known_minutes: float | None = Field(ge=0)
    minutes_covered_matches: int = Field(ge=0)
    statistics: PlayerContributionStatistics
    per90: PlayerRates
    per90_match_ids: list[int]
    comparison_evidence: dict[str, ComparisonEvidence]


class PlayerIdentity(Contract):
    player_id: int = Field(gt=0)
    player: str
    aliases: list[str]
    team_id: int = Field(gt=0)
    team: str
    positions: list[str]
    aggregate: PlayerAggregate


class Contribution(Contract):
    match_id: int = Field(gt=0)
    match_date: str
    home_team: str
    away_team: str
    team_id: int
    team: str
    positions: list[str]
    position_history: list[PositionSpell]
    minutes: float | None = Field(ge=0)
    appeared: bool | None
    minutes_status: str
    minutes_provenance: str
    statistics: PlayerContributionStatistics
    per90: PlayerRates
    model_id: str | None


class MatchGap(Contract):
    match_id: int
    status: str


class PlayerContext(Contract):
    competition_id: int
    season_id: int
    team_id: int
    requested_match_ids: list[int]
    included_match_ids: list[int]
    failed_matches: list[MatchGap]
    lineups_unavailable_match_ids: list[int]
    available_catalogue_matches: int
    sample_label: str


class PlayerModel(Contract):
    status: Literal['available', 'unavailable']
    model_id: str | None
    training_matches: int | None
    held_out_matches: int | None
    shot_zones: int | None
    total_zones: int | None
    limitations: str


class PlayerCatalogue(Contract):
    context: PlayerContext
    definitions: dict[str, str]
    model: PlayerModel
    players: list[PlayerIdentity]


class PlayerProfile(Contract):
    context: PlayerContext
    definitions: dict[str, str]
    model: PlayerModel
    identity: PlayerIdentity
    matches: list[Contribution]
