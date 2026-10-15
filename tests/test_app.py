"""Exercise selection and network failure messages without live requests."""

from pathlib import Path

import pandas as pd
import streamlit as st
import pytest
from streamlit.testing.v1 import AppTest

from src import data_loader

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def competition_catalogue(monkeypatch):
    monkeypatch.setattr(data_loader, "load_competitions", lambda: pd.DataFrame([
        {"competition_id": 9, "season_id": 281, "competition_name": "Bundesliga", "season_name": "2023/24"},
        {"competition_id": 1, "season_id": 2, "competition_name": "Other", "season_name": "2020"}]))


def test_team_selection(monkeypatch):
    st.cache_data.clear()
    monkeypatch.setattr(data_loader, "load_matches", lambda *args: pd.DataFrame([
        {"match_id": 1, "match_date": "2024-01-01", "home_team": "A", "away_team": "B"}]))
    monkeypatch.setattr(data_loader, "load_events", lambda match_id: pd.DataFrame([
        {"type": "Pass", "team": "A", "player": "Alice", "location": [1, 2], "pass_end_location": [3, 4]},
        {"type": "Pass", "team": "B", "player": "Bob", "pass_outcome": "Out"}]))
    try:
        app = AppTest.from_file(APP, default_timeout=30).run()
        assert not app.exception
        assert app.metric[1].value == "1"
        app.segmented_control[0].set_value("B").run()
        assert not app.exception
        assert app.metric[1].value == "0"
        app.segmented_control[1].set_value("Team shots").run()
        assert not app.exception
        app.segmented_control[1].set_value("Player statistics").run()
        assert not app.exception
        assert len(app.dataframe) == 1
        app.segmented_control[1].set_value("Progressive passing").run()
        assert not app.exception
        assert app.dataframe[0].value.iloc[0]["Progressive attempts"] == 0
        app.number_input[0].set_value(1.0).run()
        assert not app.exception
        app.selectbox[1].select(1).run()
        assert not app.exception
        assert app.selectbox[2].value == 2
    finally:
        st.cache_data.clear()


def test_match_loading_failure(monkeypatch):
    st.cache_data.clear()
    def fail(*args):
        raise ConnectionError("offline")
    monkeypatch.setattr(data_loader, "load_matches", fail)
    try:
        app = AppTest.from_file(APP, default_timeout=30).run()
        assert not app.exception
        assert "Could not load matches" in app.error[0].value
    finally:
        st.cache_data.clear()
