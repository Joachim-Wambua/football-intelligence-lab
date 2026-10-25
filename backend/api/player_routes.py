"""Versioned player-intelligence endpoints over an explicit bounded match sample."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.api.routes import Provider, PositiveId
from backend.api.player_schemas import PlayerCatalogue, PlayerProfile
from backend.api.player_service import PlayerCollectionService, get_player_service
from backend.api.xt_model import get_xt_model

router = APIRouter()
Id = Annotated[int, Query(gt=0)]
MatchIds = Annotated[list[Annotated[int, Query(gt=0)]], Query(min_length=1, max_length=5)]
Service = Annotated[PlayerCollectionService, Depends(get_player_service)]


def selected_collection(provider, service, competition_id, season_id, team_id, match_ids):
    """Load only a validated explicit sample; model failure leaves observed data usable."""
    try:
        active = get_xt_model()
    except HTTPException as error:
        if error.status_code != 503:
            raise
        active = None
    return service.collection(provider, competition_id, season_id, team_id, match_ids, active)


@router.get('/player-intelligence/players', response_model=PlayerCatalogue)
def catalogue(provider: Provider, service: Service, competition_id: Id, season_id: Id,
              team_id: Id, match_ids: MatchIds):
    """Catalogue roster and event-observed identities, including unused substitutes."""
    return selected_collection(provider, service, competition_id, season_id, team_id, match_ids)


@router.get('/player-intelligence/players/{player_id}', response_model=PlayerProfile)
def profile(player_id: PositiveId, provider: Provider, service: Service, competition_id: Id,
            season_id: Id, team_id: Id, match_ids: MatchIds):
    """Expose per-match numerators and qualified pooled per90 for one provider ID."""
    collection = selected_collection(provider, service, competition_id, season_id, team_id, match_ids)
    if player_id not in collection['profiles']:
        raise HTTPException(404, 'Player not found in this selected team collection')
    return {**collection, **collection['profiles'][player_id]}
