"""Read-only endpoints adapting shared metrics to stable response schemas."""

from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from src.metrics import passing_summary, player_statistics, select_passes, select_shots
from backend.api.provider import CachedProvider, get_provider
from backend.api.schemas import (Competition, Error, Health, Match, MatchSummary, Pass,
                                 PlayerStatistics, TeamSummary)
from backend.api.serialization import records

router = APIRouter(responses={404: {"model": Error, "description": "Resource not found"},
    502: {"model": Error, "description": "Provider unavailable or invalid data"},
    504: {"model": Error, "description": "Provider timeout"}})
Provider = Annotated[CachedProvider, Depends(get_provider)]
PositiveId = Annotated[int, Path(gt=0)]


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
def passes(match_id: PositiveId, player_id: PositiveId, provider: Provider):
    """Return one player's passes; known players with no passes return []."""
    events = provider.events(match_id)
    subset = events.loc[events.player_id.eq(player_id)]
    if subset.empty:
        raise HTTPException(404, "Player not found in this match")
    # Filter by numeric ID first so names cannot select another player.
    prepared = select_passes(subset, subset.team.iloc[0])
    return [Pass.model_validate(row) for row in records(prepared)]
