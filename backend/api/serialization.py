"""Normalize pandas/numpy scalars before validating HTTP response contracts."""

import json
import pandas as pd


def records(frame: pd.DataFrame) -> list[dict]:
    """Convert missing values and +/-infinity to JSON null, dates to ISO strings.

    pandas handles numpy scalar types and nested coordinate lists. Its JSON
    encoder maps nonfinite numbers to null rather than emitting invalid JSON.
    """
    return json.loads(frame.to_json(orient="records", date_format="iso"))
