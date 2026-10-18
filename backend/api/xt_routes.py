"""Read-only xT model/valuation endpoints, backed by shared Python research code."""

from typing import Annotated
from fastapi import APIRouter, Depends, Query

from backend.api.routes import Provider, PositiveId, team_events
from backend.api.schemas import Error
from backend.api.serialization import records
from backend.api.xt_model import ActiveXT, get_xt_model
from backend.api.xt_schemas import XTModelInfo, XTPlayers, XTPlayer, XTActions, XTAction
from src.xt_summary import valued_moves, player_xt_summary

router = APIRouter(responses={404: {'model': Error}, 502: {'model': Error},
    503: {'model': Error, 'description': 'Missing, corrupt or incompatible xT artifact'}, 504: {'model': Error}})
Model = Annotated[ActiveXT, Depends(get_xt_model)]


def team_moves(provider, match_id, team_id, active):
    """Value all team move attempts once, retaining provider-order event positions.

    Source is the existing StatsBomb adapter, whose contract is acting-team attack
    right. Individual malformed coordinates yield null scores, not request failure.
    """
    events = provider.events(match_id).reset_index(drop=True)
    events['event_index'] = range(len(events))
    subset, _ = team_events(events, team_id)
    return valued_moves(subset, active.model)


@router.get('/xt/model', response_model=XTModelInfo)
def model_info(active: Model):
    """Return the actual grid and model coverage without contacting StatsBomb."""
    return active.info


@router.get('/matches/{match_id}/teams/{team_id}/xt/players', response_model=XTPlayers)
def players(match_id: PositiveId, team_id: PositiveId, provider: Provider, active: Model):
    """Rank by positive xT then net xT and ID; entirely unrated players sort last.

    Aggregation uses all team moves, not a paginated action sample. Totals are
    model-based and signed; they are neither per-90 values nor scouting ratings.
    """
    summary = player_xt_summary(team_moves(provider, match_id, team_id, active))
    summary = summary.sort_values(['positive_xt', 'net_xt', 'player_id'],
        ascending=[False, False, True], na_position='last')
    return XTPlayers(model_id=active.info.model_id, match_id=match_id, team_id=team_id,
        players=[XTPlayer.model_validate(row) for row in records(summary)])


@router.get('/matches/{match_id}/teams/{team_id}/xt/actions', response_model=XTActions)
def actions(match_id: PositiveId, team_id: PositiveId, provider: Provider, active: Model,
            limit: Annotated[int, Query(ge=1, le=500)] = 200,
            offset: Annotated[int, Query(ge=0)] = 0,
            player_id: Annotated[int | None, Query(gt=0)] = None):
    """Return a bounded provider-order page of pass/carry attempts and nullable xT.

    Failed/unscorable moves remain inspectable with null xT; shots never appear.
    total is after optional player filtering, before paging. Player totals are
    served separately so a partial overlay cannot be mistaken for full-match data.
    """
    moves = team_moves(provider, match_id, team_id, active)
    if player_id is not None:
        moves = moves.loc[moves.player_id.eq(player_id)]
    page = moves.iloc[offset:offset + limit].rename(columns={'xT': 'xt'})
    return XTActions(model_id=active.info.model_id, match_id=match_id, team_id=team_id,
        total=len(moves), offset=offset, limit=limit,
        actions=[XTAction.model_validate(row) for row in records(page)])
