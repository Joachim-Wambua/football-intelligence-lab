"""Evidence-only workspace adapters; no fitting or tactical inference."""
from typing import Annotated

from fastapi import APIRouter, Query, HTTPException

from backend.api.routes import Provider, PositiveId, team_events, progressive_rankings
from backend.api.schemas import Contract
from backend.api.serialization import records
from backend.api.xt_model import get_xt_model
from backend.api.xt_routes import players as xt_players
from src.metrics import select_shots


router = APIRouter()


class Shot(Contract):
    match_id: int
    event_index: int
    id: str | None = None
    team_id: int
    team: str
    player_id: int | None = None
    player: str | None = None
    period: int | None = None
    minute: int | None = None
    x: float | None
    y: float | None
    goal: bool
    xg: float | None


class Observation(Contract):
    metric: str
    definition: str
    value: float | None
    denominator: int | None = None
    player_id: int | None = None
    player: str | None = None
    model_id: str | None = None


class Insights(Contract):
    match_id: int
    team_id: int
    observations: list[Observation]
    xt_status: str


@router.get('/matches/{match_id}/shots', response_model=list[Shot])
def shots(match_id: PositiveId, provider: Provider,
          team_id: Annotated[int | None, Query(gt=0)] = None):
    """Expose recorded shots in provider order, including unplottable events.

    StatsBomb uses a 120 by 80, top-left-origin pitch with the acting team
    attacking right in every period. No half/home-team reflection is needed.
    select_shots owns geometry and xG validation: e.g. xG .3 is retained,
    an absent or out-of-range probability stays null, never zero. Event index
    identifies rows even when provider event IDs are missing. Own-goal events
    are not Shot events; shootouts remain included and identifiable by period.
    """
    events = provider.events(match_id).reset_index(drop=True)
    events['event_index'] = range(len(events))
    if team_id is not None:
        events, _ = team_events(events, team_id)
    prepared = []
    for identity in events[['team_id', 'team']].dropna().drop_duplicates().itertuples(index=False):
        subset = events.loc[events.team_id.eq(identity.team_id)]
        prepared.extend(records(select_shots(subset, identity.team)))
    prepared.sort(key=lambda row: row['event_index'])
    return [Shot.model_validate({**row, 'match_id': match_id}) for row in prepared]


@router.get('/matches/{match_id}/teams/{team_id}/insights', response_model=Insights)
def insights(match_id: PositiveId, team_id: PositiveId, provider: Provider):
    """Return verifiable evidence, with explicit denominators and model status.

    Coverage counts valid provider probabilities divided by all shots: two
    recorded values among three shots means 2/3, not three estimated values.
    Leaders reuse shared rankings; ties resolve by the documented API ordering.
    Zero completed progression yields no leader. Frozen xT failure must not
    hide observed evidence. These counts imply neither tactics nor causality.
    """
    events, team = team_events(provider.events(match_id), team_id)
    prepared = select_shots(events, team)
    observations = [
        Observation(metric='shots', value=len(prepared), definition='Count of recorded Shot events; all periods, excluding own-goal events.'),
        Observation(metric='xg_coverage', value=int(prepared.xg.notna().sum()), denominator=len(prepared), definition='Shots with valid provider xG / all recorded shots; 0/0 means no shots, not complete coverage.'),
        Observation(metric='recorded_xg', value=records(prepared[['xg']].sum(min_count=1).to_frame().T)[0]['xg'], denominator=int(prepared.xg.notna().sum()), definition='Sum of available provider xG only; denominator is covered shots. Null when none. Provider model estimate, not observed goals.')]
    ranking = progressive_rankings(match_id, team_id, provider)
    if ranking.players and ranking.players[0].completed_progressive > 0:
        leader = ranking.players[0]
        observations.append(Observation(metric='completed_progressive_leader', value=leader.completed_progressive, denominator=leader.passes, player_id=leader.player_id, player=leader.player, definition='Completed passes reducing distance to (120,40) by >=10 metres-equivalent on assumed 105x68m pitch / all player passes. Order: completed count, attempts, ID.'))
    status = 'available'
    try:
        ranked = xt_players(match_id, team_id, provider, get_xt_model())
        rated = [row for row in ranked.players if row.positive_xt is not None]
        if rated:
            leader = rated[0]
            observations.append(Observation(metric='experimental_positive_xt_leader', value=leader.positive_xt, denominator=leader.rated_action_count, player_id=leader.player_id, player=leader.player, model_id=ranked.model_id, definition='Experimental frozen xT: sum of positive destination-minus-origin values over rated successful passes/carries; denominator rated actions. Order: positive xT, net xT, ID. Small training sample; not a player rating.'))
    except HTTPException as error:
        if error.status_code != 503:
            raise
        status = 'unavailable'
    return Insights(match_id=match_id, team_id=team_id, observations=observations, xt_status=status)
