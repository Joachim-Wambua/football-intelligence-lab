"""Future benchmark-v1 contracts only; no public endpoint is registered."""
from typing import Literal

from pydantic import Field, model_validator

from backend.api.schemas import Contract


class BenchmarkPercentile(Contract):
    """Unavailable ranks remain null and carry their eligibility explanation."""
    metric: str
    value_per90: float | None
    percentile: float | None = Field(ge=0, le=100)
    sample_size: int = Field(ge=0)
    status: Literal['available', 'unavailable', 'low_exposure', 'insufficient_samples']
    higher_is_better: bool

    @model_validator(mode='after')
    def validate_availability(self):
        """Prevent an unavailable rank from being serialized as a measured zero."""
        if (self.status == 'available') != (self.percentile is not None):
            raise ValueError('Percentile must be present exactly when available')
        if self.status == 'available' and (self.value_per90 is None or self.sample_size == 0):
            raise ValueError('Available rank requires a value and reference members')
        return self


class BenchmarkSummary(Contract):
    """Explicit population makes a percentile interpretable and reproducible.

    Reference members are player/team pairs, not display names. A transfer can
    contribute two stints; this policy must be visible before any visualization.
    Eligibility and value qualification are Python-owned offline calculations.
    """
    schema_version: Literal['benchmark-v1']
    dataset_version: str
    competition_id: int = Field(gt=0)
    season_id: int = Field(gt=0)
    team_id: int = Field(gt=0)
    player_id: int = Field(gt=0)
    position_group: str | None
    match_ids: list[int]
    reference_members: list[tuple[int, int]]
    minimum_minutes: float = Field(ge=0)
    minimum_samples: int = Field(gt=0)
    tie_policy: Literal['mid_distribution_exact_ties']
    percentiles: list[BenchmarkPercentile]
    limitations: list[str]
