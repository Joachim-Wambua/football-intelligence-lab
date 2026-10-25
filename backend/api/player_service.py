"""Bounded, cached player collections, separate from HTTP adapters and training."""
from copy import deepcopy
from functools import lru_cache
from threading import RLock

import pandas as pd
from cachetools import TTLCache
from fastapi import HTTPException

from backend.api.serialization import records
from src.player_analytics import match_players, aggregate_player, DEFINITIONS, COUNT_METRICS, NULLABLE_METRICS, per90
from src.playing_time import MINUTES_PROVENANCE


class PlayerCollectionService:
    """Prepare at most five selected files on a cold request, cache eight collections.

    The raw provider already caches events/lineups. This additional 15-minute
    cache shares ID catalogues and all profiles, avoiding re-aggregation on every
    player click. Keys include provider identity, explicit context, canonical
    match IDs and frozen model ID. Lock spans preparation; no model fitting.
    Returned snapshots are copied so clients cannot mutate cached calculations.
    """
    def __init__(self, *, timer=None):
        options = {} if timer is None else {'timer': timer}
        self.cache = TTLCache(maxsize=8, ttl=900, **options)
        self.lock = RLock()

    def collection(self, provider, competition_id, season_id, team_id, match_ids, active):
        if not 1 <= len(match_ids) <= 5 or len(set(match_ids)) != len(match_ids):
            raise HTTPException(422, 'Select one to five distinct match IDs')
        ids = tuple(sorted(match_ids))
        key = (provider, competition_id, season_id, team_id, ids, active.info.model_id if active else None)
        with self.lock:
            if key not in self.cache:
                self.cache[key] = self._prepare(provider, competition_id, season_id, team_id, ids, active)
            return deepcopy(self.cache[key])

    def _prepare(self, provider, competition_id, season_id, team_id, match_ids, active):
        """Verify catalogue membership and qualify each requested match separately."""
        competitions = provider.competitions()
        if not (competitions.competition_id.eq(competition_id) & competitions.season_id.eq(season_id)).any():
            raise HTTPException(404, 'Competition-season pair not found')
        catalogue = provider.matches(competition_id, season_id)
        metadata = {int(row['match_id']): row for row in records(catalogue)}
        if any(match_id not in metadata for match_id in match_ids):
            raise HTTPException(404, 'Selected match is outside the competition-season catalogue')
        included, failed, missing_lineups, prepared, rosters = [], [], [], {}, {}
        for match_id in sorted(match_ids, key=lambda value: (str(metadata[value]['match_date']), value)):
            try:
                events = provider.events(match_id)
            except HTTPException as error:
                failed.append({'match_id': match_id, 'status': f'events_unavailable_{error.status_code}'})
                continue
            if not events.team_id.eq(team_id).any():
                failed.append({'match_id': match_id, 'status': 'team_not_in_match'})
                continue
            try:
                lineups = provider.lineups(match_id)
            except HTTPException:
                lineups = pd.DataFrame()
            if 'team_id' not in lineups or not lineups.team_id.eq(team_id).any():
                missing_lineups.append(match_id)
            rosters[match_id] = lineups
            included.append(match_id)
            prepared[match_id] = match_players(events, lineups, metadata[match_id], team_id,
                active.model if active else None, active.info.model_id if active else None)
        if not included:
            raise HTTPException(404, 'No selected match contains available evidence for this team')
        identities = sorted({player_id for rows in prepared.values() for player_id in rows})
        players, profiles = [], {}
        for player_id in identities:
            known = [rows[player_id] for rows in prepared.values() if player_id in rows]
            latest = known[-1]
            contributions = []
            for match_id in included:
                if player_id in prepared[match_id]:
                    contributions.append(prepared[match_id][player_id])
                else:
                    # A complete team squad explicitly omits this ID; without a
                    # lineup, no-touch participation remains unknown rather than 0.
                    roster_known = match_id not in missing_lineups
                    statistics = {**dict.fromkeys(COUNT_METRICS, 0), **dict.fromkeys(NULLABLE_METRICS, None)}
                    contributions.append({**metadata[match_id], 'team_id': team_id, 'team': latest['team'],
                        'positions': [], 'position_history': [], 'minutes': 0 if roster_known else None,
                        'appeared': False if roster_known else None,
                        'minutes_status': 'not_in_squad' if roster_known else 'lineups_unavailable',
                        'minutes_provenance': MINUTES_PROVENANCE, 'statistics': statistics,
                        'per90': per90(statistics, None), 'model_id': active.info.model_id if active else None})
            aggregate = aggregate_player(contributions, incomplete_collection=bool(failed))
            identity = {field: latest[field] for field in ('player_id', 'player', 'team_id', 'team')}
            identity.update(aliases=sorted({name for row in known for name in row['aliases']}),
                positions=sorted({name for row in known for name in row['positions']}), aggregate=aggregate)
            players.append(identity)
            profiles[player_id] = {'identity': identity, 'matches': contributions}
        players.sort(key=lambda row: (row['player'].casefold(), row['player_id']))
        info = active.info if active else None
        return {'context': {'competition_id': competition_id, 'season_id': season_id, 'team_id': team_id,
            'requested_match_ids': list(match_ids), 'included_match_ids': included, 'failed_matches': failed,
            'lineups_unavailable_match_ids': missing_lineups, 'available_catalogue_matches': len(catalogue),
            'sample_label': 'Explicit selected-match collection; not a full league season'},
            'definitions': DEFINITIONS,
            'model': {'status': 'available' if active else 'unavailable', 'model_id': info.model_id if info else None,
                'training_matches': len(info.coverage.train_ids) if info else None,
                'held_out_matches': len(info.coverage.held_out_ids) if info else None,
                'shot_zones': info.coverage.shot_zones if info else None, 'total_zones': info.coverage.total_zones if info else None,
                'limitations': 'Experimental, frozen offline fit; sparse Leverkusen training sample. Not calibrated possession-goal probabilities, player ratings or league-wide comparisons.'},
            'players': players, 'profiles': profiles}


@lru_cache(maxsize=1)
def get_player_service():
    """Share bounded aggregation state across player catalogue/profile requests."""
    return PlayerCollectionService()
