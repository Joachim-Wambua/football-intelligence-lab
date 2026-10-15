# Football Intelligence Lab

A modular Streamlit dashboard for competition, season and match selection,
player passing maps, team shot maps, and player performance statistics.
Bundesliga 2023/24 is selected by default. No models are trained in this project.

## Run locally

Use Python 3.12 (the development environment), or a compatible newer Python.
From the project root in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed by Streamlit. Select a competition, season, match,
and team. Choose Player passing, Team shots, or Player statistics. Passing maps
offer a player selector; statistics include all players with recorded events.
The first request needs internet access; no StatsBomb account or API key is
required. Matches and event tables are cached in Streamlit for one hour, with
bounded cache sizes. Reload after a temporary connection failure.

## Structure

- `src/data_loader.py`: public StatsBomb match and event requests.
- `src/datasets.py`: shared source interface, StatsBomb adapter, and local Bayer Leverkusen data adapter.
- `src/metrics.py`: team pass filtering, coordinate extraction, completion metrics.
- `src/visualizations.py`: passing map returning a Matplotlib figure.
- `app.py`: cached loading, match/team controls, metrics, chart, and error messages.
- `tests/`: synthetic data, mocked loading, real plot rendering, and Streamlit UI tests.

## Data structures and assumptions

`load_matches()` returns a pandas DataFrame with one row per available match,
sorted by `match_date` and `match_id`. The UI uses integer `match_id` values
as identifiers and `home_team` / `away_team` strings as labels.

Defaults are Bundesliga competition **9**, season **281** (2023/24).
This open-data release covers **Bayer Leverkusen matches**, not the complete
league schedule. The app lists whatever the provider currently makes available.
Other competition and season IDs can be passed to `load_matches()` in Python.

`load_events(match_id)` returns the flattened statsbombpy event DataFrame:
one row per event, string-valued `type`, `team`, and `player`, and nullable
event-specific columns. `location` and `pass_end_location` contain coordinate
lists. Input tables must contain `type` and `team`; malformed schemas raise errors.

`select_passes(events, team)` returns a copy containing only that team's `Pass`
events. It preserves provider columns and adds boolean `completed` plus numeric
`x`, `y`, `end_x`, and `end_y`. A null `pass_outcome` means a completed pass;
any explicit outcome is unsuccessful. If the entire outcome column is absent,
all passes are treated as completed, following StatsBomb's omitted-field convention.
This convention is intended for StatsBomb data, not arbitrary datasets.

Coordinates use StatsBomb's **120 × 80** pitch, with the origin at the top left
and play normalized left to right. They are provider units, not measured metres;
no home/away or second-half mirroring is applied. Nonfinite, missing, malformed,
and out-of-bounds coordinates become NaN and are omitted from the map. They still
count in passing metrics; the app reports the number omitted.

`passing_summary()` returns a dictionary with `attempted` and `completed` integer
counts and `completion_pct` on a 0–100 scale (0.0 when there are no passes).
All recorded pass types and periods are included, including set pieces and
extra time where present. Passing maps filter by team and player; there is no
open-play-only filter yet.
The map shows blue completed passes and orange unsuccessful passes, with arrows
from origin to destination. Its caller is responsible for closing the figure.

## V1 shot maps and player statistics

Team shot maps show shot origins, with stars for goals and circles for other
shots. Marker area scales with StatsBomb's supplied `shot_statsbomb_xg`; unknown
xG uses the minimum marker size. Missing coordinates are omitted only from the
map, and the UI reports omissions. No shots produces an explicit empty map.

Player statistics include attempted/completed passes, completion percentage,
shots, shot goals, recorded xG, successful dribbles (`Complete`), and successful
interceptions (`Won`, `Success`, `Success In Play`, or `Success Out`). Players
are discovered from named events, so unused substitutes and players with no
named events are absent. Goals exclude own-goal events. No minutes, ratings,
assists, or per-90 estimates are inferred. Unknown or out-of-range xG remains
missing; totals sum recorded values only and the shot view reports coverage.
StatsBomb supplies xG; the project does not fit a model. All periods are included.

## Adding BVB datasets later

`DatasetSource` defines three methods: `competitions()`,
`matches(competition_id, season_id)`, and `events(match_id)`. Analytics and plots
consume the same normalized pandas tables regardless of the source. Cache keys
include the dataset name so matching IDs in different sources cannot collide.

The included `LocalDatasetSource` reads JSON arrays of flattened records. Add:

```text
data/bvb/competitions.json
data/bvb/matches.json
data/bvb/events/<match_id>.json
```

The dashboard offers Local BVB dataset when `competitions.json` exists. No BVB
data is bundled or fabricated. Restart the app or clear its cache after replacing
local files. Required records:

```json
// competitions.json (remove this comment in actual JSON)
[{"competition_id":9,"season_id":281,"competition_name":"Bundesliga","season_name":"2023/24"}]
```

```json
[{"competition_id":9,"season_id":281,"match_id":1,"match_date":"2024-01-01","home_team":"BVB","away_team":"Opponent"}]
```

```json
[{"type":"Pass","team":"BVB","player":"Player name","location":[40,30],"pass_end_location":[60,35],"pass_outcome":null}]
```

The latter two examples describe `matches.json` and `events/1.json`. Dates use
ISO format; IDs are integers. Events require `type` and `team`; supply `player`
for player views. Optional shot fields are `shot_outcome` and
`shot_statsbomb_xg`, using the conventions above. Raw StatsBomb nested JSON or
another provider's data needs an adapter before use: normalize team/player/type
names, outcomes, coordinate scale and attacking direction. Do not apply StatsBomb
completion semantics to another provider without converting its outcomes first.

## Tests

### Progressive passing

The existing Analysis selector now includes Progressive passing, with a configurable
threshold, player comparison table, stacked count chart and team/player pass map.
The frontend stays in the existing Streamlit script. Analytics live in
`src/progressive.py`, and figures in `src/progressive_visualizations.py`; neither
imports Streamlit or performs data loading.

The attacking goal centre is **(120, 40)**. For a point `(x, y)`:

```text
d_sb = sqrt((120 - x)^2 + (40 - y)^2)
d_m  = sqrt(((120 - x) * L/120)^2 + ((40 - y) * W/80)^2)
progression = distance(start) - distance(end)
```

`distance_to_goal(location)` returns raw StatsBomb units. Passing a
`ProgressionConfig` returns metres-equivalent, assuming pitch dimensions `L=105`
and `W=68` metres by default. These are estimates on an assumed pitch, not measured
match distances. Scale each axis **before** computing the Euclidean norm; do not
multiply the raw norm by one conversion factor. Both raw and scaled distances and
signed reductions are retained in the prepared pass table.

Default classification is **progression_m >= 10.0**, inclusive. This is an explicit
project definition, not a claimed StatsBomb or other provider standard. Configure
`ProgressionConfig(threshold_m=..., pitch_length_m=..., pitch_width_m=...)` in Python;
the UI exposes the threshold and states the default pitch assumption. All parameters
must be finite and positive. All pass types and recorded periods remain included.

`progressive` describes geometry regardless of outcome; `completed_progressive`
requires both qualifying geometry and StatsBomb completion semantics. Incomplete
passes use their recorded endpoints and describe attempted progression, not retained
possession or value created. Backward reductions remain negative. A lateral pass can
qualify if it moves sufficiently closer to the goal centre; a positive x gain alone
does not guarantee qualification. No additional forward-x constraint is imposed.

Malformed endpoints (not exactly two numeric, nonboolean, finite, in-bounds
coordinates) give missing progression, `valid_geometry=False`, and False flags.
They are unclassified, rather than known nonprogressive. All attempts stay in the
comparison denominator; valid geometry counts expose coverage. Named passers only
appear in the table; players with no passes are absent. Net progression sums signed
reductions for both outcomes and is missing when no geometry is valid. This is not
completed progression or per-90 output. Maps show only qualifying attempts with
separate completed/incomplete colors. The count chart splits the same categories.

Future BVB adapters must supply the same attacking-left-to-right StatsBomb coordinate
convention and normalized outcomes before using these functions.

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Tests run offline using synthetic tables and mocked provider calls. They verify
filtering, completion semantics, empty inputs, invalid coordinates, default IDs,
plot rendering, team selection, and a loading failure message. They do not verify
live provider availability or guarantee that upstream schemas never change.

## Data source and usage

Data provided by **StatsBomb** through [StatsBomb Open Data](https://github.com/statsbomb/open-data)
and [statsbombpy](https://github.com/statsbomb/statsbombpy).
See the repository's current licence and attribution requirements before sharing
analysis or using data commercially; published work should credit StatsBomb and
follow its logo requirements. The
[Bundesliga release announcement](https://blogarchive.statsbomb.com/de/neuigkeiten/freie-daten-bayer-leverkusen-bundesliga-meister/)
describes the coverage and IDs. Plotting follows the
[mplsoccer passing-arrow API](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_arrows.html).
