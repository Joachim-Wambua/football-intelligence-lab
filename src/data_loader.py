"""Load public StatsBomb tables without requiring API credentials."""

import pandas as pd
from statsbombpy import sb

BUNDESLIGA_COMPETITION_ID = 9
SEASON_2023_24_ID = 281


def load_competitions() -> pd.DataFrame:
    """Return available competition-season pairs, with Bundesliga 2023/24 first."""
    competitions = sb.competitions().copy()
    competitions["_default"] = ~(
        competitions["competition_id"].eq(BUNDESLIGA_COMPETITION_ID)
        & competitions["season_id"].eq(SEASON_2023_24_ID)
    )
    return competitions.sort_values(
        ["_default", "competition_name", "season_name"]
    ).drop(columns="_default").reset_index(drop=True)


def load_matches(
    competition_id: int = BUNDESLIGA_COMPETITION_ID,
    season_id: int = SEASON_2023_24_ID,
) -> pd.DataFrame:
    """Return available matches, ordered by date, with one row per match.

    Open data coverage can be partial. Team columns contain names, and
    match_id is the stable identifier used to fetch events.
    """
    matches = sb.matches(competition_id=competition_id, season_id=season_id)
    return matches.sort_values(["match_date", "match_id"]).reset_index(drop=True)


def load_events(match_id: int) -> pd.DataFrame:
    """Return flattened events: one row per event, with nullable attributes.

    StatsBomb locations remain list-valued columns; no coordinate conversion
    or event filtering is applied. Network and provider errors propagate.
    """
    return sb.events(match_id=int(match_id), split=False, flatten_attrs=True)
