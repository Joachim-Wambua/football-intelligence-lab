"""Data-source boundary for open data and future normalized BVB datasets."""

from pathlib import Path
from typing import Protocol

import pandas as pd

from src import data_loader


class DatasetSource(Protocol):
    """Sources expose competition-season, match and flattened event tables."""

    def competitions(self) -> pd.DataFrame: ...
    def matches(self, competition_id: int, season_id: int) -> pd.DataFrame: ...
    def events(self, match_id: int) -> pd.DataFrame: ...


class StatsBombSource:
    """Adapter for public StatsBomb data; credentials are not needed."""

    def competitions(self) -> pd.DataFrame:
        """List published competition-season pairs."""
        return data_loader.load_competitions()

    def matches(self, competition_id: int, season_id: int) -> pd.DataFrame:
        """List available matches in the requested season."""
        return data_loader.load_matches(competition_id, season_id)

    def events(self, match_id: int) -> pd.DataFrame:
        """Read flattened match events."""
        return data_loader.load_events(match_id)


class LocalDatasetSource:
    """Read normalized JSON records from a directory, including future BVB data.

    Files: competitions.json, matches.json, events/<match_id>.json.
    Provider-specific raw data must first be converted to the documented schema.
    """

    def __init__(self, root: Path):
        self.root = Path(root)

    def competitions(self) -> pd.DataFrame:
        """Read competition-season metadata."""
        return pd.read_json(self.root / "competitions.json")

    def matches(self, competition_id: int, season_id: int) -> pd.DataFrame:
        """Filter local matches by both identifiers."""
        matches = pd.read_json(self.root / "matches.json")
        return matches.loc[
            matches["competition_id"].eq(competition_id)
            & matches["season_id"].eq(season_id)
        ].sort_values(["match_date", "match_id"]).reset_index(drop=True)

    def events(self, match_id: int) -> pd.DataFrame:
        """Read a match's normalized events, preserving coordinate lists."""
        return pd.read_json(self.root / "events" / f"{int(match_id)}.json")
