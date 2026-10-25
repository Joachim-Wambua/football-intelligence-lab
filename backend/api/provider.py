"""Bounded, thread-safe provider cache independent of Streamlit."""

from functools import lru_cache
from threading import RLock

from cachetools import TTLCache
from fastapi import HTTPException
from requests import HTTPError, Timeout

from src.datasets import StatsBombSource


class CachedProvider:
    """Cache successful tables for one hour, with at most 64 entries per process.

    Lock spans cache misses to avoid duplicate downloads. Returns independent
    frames; failed requests are never cached. Workers have separate caches.
    """

    def __init__(self, source=None, *, ttl=3600, maxsize=64, timer=None):
        self.source = source if source is not None else StatsBombSource()
        options = {} if timer is None else {"timer": timer}
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl, **options)
        self.lock = RLock()

    def _load(self, method, *args):
        key = (method, *args)
        with self.lock:
            if key not in self.cache:
                try:
                    frame = getattr(self.source, method)(*args)
                except Timeout as exc:
                    raise HTTPException(504, "Data provider timed out") from exc
                except HTTPError as exc:
                    status = 404 if exc.response is not None and exc.response.status_code == 404 else 502
                    message = "Resource not found" if status == 404 else "Data provider unavailable"
                    raise HTTPException(status, message) from exc
                except Exception as exc:
                    raise HTTPException(502, "Data provider unavailable") from exc
                self.cache[key] = frame.copy(deep=True)
            # pandas deep copies do not clone nested lists, but API consumers
            # only read source list values and add independent scalar columns.
            return self.cache[key].copy(deep=True)

    def competitions(self):
        """Read competition-season metadata."""
        return self._load("competitions")

    def matches(self, competition_id, season_id):
        """Read one match catalogue."""
        return self._load("matches", competition_id, season_id)

    def events(self, match_id):
        """Read events, treating an empty table as an unknown match."""
        frame = self._load("events", match_id)
        if frame.empty:
            raise HTTPException(404, "Match not found")
        return frame


    def lineups(self, match_id):
        """Read optional squad information through the same bounded raw cache."""
        return self._load("lineups", match_id)


@lru_cache(maxsize=1)
def get_provider():
    """Lazy dependency so importing the API never contacts StatsBomb."""
    return CachedProvider()
