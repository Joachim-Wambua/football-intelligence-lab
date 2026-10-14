"""Football Intelligence Lab V1 dashboard."""
from pathlib import Path
import matplotlib.pyplot as plt
import streamlit as st
from src.datasets import StatsBombSource, LocalDatasetSource
from src.metrics import select_passes, passing_summary, select_shots, player_statistics
from src.visualizations import passing_map, shot_map

st.set_page_config(page_title="Football Intelligence Lab", layout="wide")
st.title("Football Intelligence Lab")
st.caption("V1 | Match and player analysis")
ROOT = Path(__file__).resolve().parent / "data" / "bvb"
options = ["StatsBomb open data"]
if (ROOT / "competitions.json").exists():
    options.append("Local BVB dataset")
name = st.selectbox("Dataset", options)


def source_for(name):
    """Resolve an application-controlled data source."""
    return StatsBombSource() if name == "StatsBomb open data" else LocalDatasetSource(ROOT)


@st.cache_data(ttl=3600, max_entries=4)
def competitions_for(name):
    """Cache competition-season metadata by source."""
    return source_for(name).competitions()


@st.cache_data(ttl=3600, max_entries=20)
def matches_for(name, competition, season):
    """Cache matches by source, competition and season."""
    return source_for(name).matches(competition, season)


@st.cache_data(ttl=3600, max_entries=40)
def events_for(name, match):
    """Cache events by source and match identifier."""
    return source_for(name).events(match)


try:
    competitions = competitions_for(name)
except Exception:
    st.error("Could not load competitions. Check your connection or local dataset files.")
    st.stop()
if competitions.empty:
    st.info("No competitions available.")
    st.stop()
competition_labels = competitions.set_index("competition_id")["competition_name"].to_dict()
competition = st.selectbox("Competition", competitions.competition_id.drop_duplicates().tolist(), format_func=competition_labels.get)
seasons = competitions.loc[competitions.competition_id.eq(competition)]
season_labels = seasons.set_index("season_id")["season_name"].to_dict()
season = st.selectbox("Season", list(season_labels), format_func=season_labels.get)
if competition == 9 and season == 281 and name == "StatsBomb open data":
    st.caption("Bundesliga 2023/24 coverage: Bayer Leverkusen matches, not the complete league.")
try:
    matches = matches_for(name, int(competition), int(season))
except Exception:
    st.error("Could not load matches. Check your connection or local dataset files.")
    st.stop()
if matches.empty:
    st.info("No matches available for this competition and season.")
    st.stop()
labels = {int(r.match_id): f"{r.match_date} | {r.home_team} vs {r.away_team}" for r in matches.itertuples()}
match_id = st.selectbox("Match", list(labels), format_func=labels.get)
match = matches.loc[matches.match_id.eq(match_id)].iloc[0]
teams = [match.home_team, match.away_team]
team = st.segmented_control("Team", teams, default=teams[0], required=True)
try:
    events = events_for(name, match_id)
except Exception:
    st.error("Could not load match events. Check your connection or local dataset files.")
    st.stop()
summary = passing_summary(select_passes(events, team))
with st.container(horizontal=True):
    st.metric("Team passes attempted", summary["attempted"])
    st.metric("Team passes completed", summary["completed"])
    st.metric("Team completion rate", f"{summary['completion_pct']:.1f}%")
view = st.segmented_control("Analysis", ["Player passing", "Team shots", "Player statistics"], default="Player passing", required=True)
if view == "Player passing":
    players = player_statistics(events, team)["Player"].tolist()
    if not players:
        st.info("No named player events available for this team.")
    else:
        player = st.selectbox("Player", players)
        passes = select_passes(events, team, player)
        summary = passing_summary(passes)
        st.write(f"{summary['attempted']} passes | {summary['completed']} completed | {summary['completion_pct']:.1f}% completion")
        fig = passing_map(passes, f"{player} - passing map")
        try:
            st.pyplot(fig, alt=f"{player} pass trajectories colored by completion")
        finally:
            plt.close(fig)
        omitted = passes[["x", "y", "end_x", "end_y"]].isna().any(axis=1).sum()
        if omitted:
            st.info(f"{omitted} passes omitted from map due to invalid coordinates; metrics include them.")
elif view == "Team shots":
    shots = select_shots(events, team)
    st.write(f"{len(shots)} shots | {int(shots.goal.sum())} shot goals")
    covered = shots.xg.notna().sum()
    st.write(f"Recorded xG: {shots.xg.sum():.2f} ({covered}/{len(shots)} shots covered)" if covered else "Recorded xG: unavailable")
    fig = shot_map(shots, f"{team} - shot map")
    try:
        st.pyplot(fig, alt=f"{team} shot locations with distinct goal markers and areas scaled by xG")
    finally:
        plt.close(fig)
    omitted = shots[["x", "y"]].isna().any(axis=1).sum()
    if omitted:
        st.info(f"{omitted} shots omitted from map due to invalid coordinates; statistics include them.")
    st.caption("Marker area scales with provider xG. Unknown xG uses minimum marker size.")
else:
    st.dataframe(player_statistics(events, team), hide_index=True, alt="Selected team player event statistics")
    st.caption("Players with recorded events only. No minutes or per-90 estimates. Unknown xG is blank.")
st.caption("StatsBomb coordinates: 120 x 80, attacking left to right. All periods and pass types included.")
st.caption("Goals count shot goals, excluding own-goal events. Provider xG is used; no models are trained here.")
st.caption("Data: StatsBomb | https://github.com/statsbomb/open-data | Usage terms in README.")
