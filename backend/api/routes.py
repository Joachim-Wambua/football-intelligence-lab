"""Read-only endpoints adapting shared metrics to stable response schemas."""

from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from src.metrics import passing_summary, player_statistics, select_passes, select_shots
from src.progressive import ProgressionConfig, progressive_passes, player_progression_comparison
from backend.api.provider import CachedProvider, get_provider
from backend.api.schemas import (Competition, Error, Health, Match, MatchSummary, Pass,
                                 PlayerStatistics, TeamSummary, TeamProgression,
                                 PlayerProgression, ProgressionDefinition)
from backend.api.serialization import records

router = APIRouter(responses={404: {"model": Error, "description": "Resource not found"},
    502: {"model": Error, "description": "Provider unavailable or invalid data"},
    504: {"model": Error, "description": "Provider timeout"}})
Provider = Annotated[CachedProvider, Depends(get_provider)]
PositiveId = Annotated[int, Path(gt=0)]
Threshold = Annotated[float, Query(gt=0, allow_inf_nan=False,
    description="Inclusive reduction in metres-equivalent distance to goal; assumed 105 x 68 m pitch.")]
DEFAULT_THRESHOLD = ProgressionConfig().threshold_m


def team_events(events, team_id):
    """Validate team membership using provider IDs, never client-supplied names."""
    subset = events.loc[events.team_id.eq(team_id)]
    if subset.empty:
        raise HTTPException(404, "Team not found in this match")
    return subset, subset.team.iloc[0]


@router.get("/health", response_model=Health)
def health():
    """Process liveness only; does not probe StatsBomb."""
    return Health()


@router.get("/competitions", response_model=list[Competition])
def competitions(provider: Provider):
    """List available competition-season pairs."""
    return [Competition.model_validate(row) for row in records(provider.competitions())]


@router.get("/matches", response_model=list[Match])
def matches(provider: Provider, competition_id: Annotated[int, Query(gt=0)] = 9,
            season_id: Annotated[int, Query(gt=0)] = 281):
    """List matches; a known season with no matches returns an empty array."""
    catalogue = provider.competitions()
    if not (catalogue.competition_id.eq(competition_id) & catalogue.season_id.eq(season_id)).any():
        raise HTTPException(404, "Competition-season pair not found")
    return [Match.model_validate(row) for row in records(provider.matches(competition_id, season_id))]


@router.get("/matches/{match_id}/summary", response_model=MatchSummary)
def summary(match_id: PositiveId, provider: Provider):
    """Summarize event-observed teams using the shared passing and shot metrics."""
    events = provider.events(match_id)
    teams = []
    for row in events[["team_id", "team"]].dropna().drop_duplicates().itertuples(index=False):
        shots = select_shots(events, row.team)
        values = records(pd.DataFrame([{"recorded_xg": shots.xg.sum(min_count=1)}]))[0]
        teams.append(TeamSummary(team_id=int(row.team_id), team=row.team,
            passing=passing_summary(select_passes(events, row.team)), shots=len(shots),
            shot_goals=int(shots.goal.sum()), shots_with_xg=int(shots.xg.notna().sum()), **values))
    return MatchSummary(match_id=match_id, event_count=len(events), teams=teams)


@router.get("/matches/{match_id}/teams/{team_id}/players", response_model=list[PlayerStatistics])
def players(match_id: PositiveId, team_id: PositiveId, provider: Provider):
    """Return statistics for named event-observed players, with stable IDs."""
    events = provider.events(match_id)
    subset, team = team_events(events, team_id)
    identities = subset[["player", "player_id"]].dropna().drop_duplicates()
    stats = player_statistics(events, team).merge(identities, left_on="Player", right_on="player")
    stats = stats.rename(columns={"Passes": "passes", "Completed passes": "completed_passes",
        "Pass completion %": "pass_completion_pct", "Shots": "shots", "Goals": "goals",
        "xG": "xg", "Successful dribbles": "successful_dribbles",
        "Successful interceptions": "successful_interceptions"})
    return [PlayerStatistics.model_validate(row) for row in records(stats)]


@router.get("/matches/{match_id}/players/{player_id}/passes", response_model=list[Pass])
def passes(match_id: PositiveId, player_id: PositiveId, provider: Provider,
           threshold_m: Threshold = DEFAULT_THRESHOLD):
    """Return passes plus Python-owned progression, including incomplete attempts.

    Missing geometry gives null progression and false classification flags.
    Known players with no passes return []. The threshold matches the team
    progressive-passing endpoint; clients should send the same value to both.
    """
    events = provider.events(match_id)
    subset = events.loc[events.player_id.eq(player_id)]
    if subset.empty:
        raise HTTPException(404, "Player not found in this match")
    # Filter by numeric ID first so names cannot select another player.
    prepared = progressive_passes(subset, subset.team.iloc[0], ProgressionConfig(threshold_m=threshold_m))
    return [Pass.model_validate(row) for row in records(prepared)]


@router.get("/matches/{match_id}/teams/{team_id}/progressive-passing", response_model=TeamProgression)
def progressive_rankings(match_id: PositiveId, team_id: PositiveId, provider: Provider,
                         threshold_m: Threshold = DEFAULT_THRESHOLD):
    """Rank named passers by completed progressive count, attempts, then player ID.

    The shared comparison owns all metrics. Numeric-ID grouping here prevents
    different people with identical display names being merged into one row.
    Rankings are ordinal positions; tied counts are resolved deterministically.
    """
    events, team = team_events(provider.events(match_id), team_id)
    config = ProgressionConfig(threshold_m=threshold_m)
    prepared = progressive_passes(events, team, config)
    rows = []
    for player_id, group in prepared.dropna(subset=["player_id", "player"]).groupby("player_id", sort=True):
        comparison = player_progression_comparison(group)
        if len(comparison) != 1:
            raise HTTPException(502, "Inconsistent player names returned by provider")
        row = comparison.rename(columns={"Player": "player", "Passes": "passes",
            "Valid geometry": "valid_geometry", "Progressive attempts": "progressive_attempts",
            "Completed progressive": "completed_progressive", "Progressive %": "progressive_pct",
            "Net progression (m equivalent)": "net_progression_m"})
        rows.append({"player_id": int(player_id), **records(row)[0]})
    rows.sort(key=lambda row: (-row["completed_progressive"], -row["progressive_attempts"], row["player_id"]))
    players = [PlayerProgression(rank=index, **row) for index, row in enumerate(rows, start=1)]
    return TeamProgression(match_id=match_id, team_id=team_id,
        definition=ProgressionDefinition(threshold_m=config.threshold_m,
            pitch_length_m=config.pitch_length_m, pitch_width_m=config.pitch_width_m), players=players)
