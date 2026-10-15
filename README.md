# Football Intelligence Lab

A modular Streamlit dashboard for competition, season and match selection,
player passing maps, team shot maps, and player performance statistics.
Bundesliga 2023/24 is selected by default. No models are trained in this project.

## Run locally

Use Python 3.12 (the development environment), or a compatible newer Python.
From the project root in PowerShell:

```powershell
python -m venv .venv
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit. Select a competition, season, match,
and team. Choose Player passing, Team shots, or Player statistics. Passing maps
offer a player selector; statistics include all players with recorded events.
The first request needs internet access; no StatsBomb account or API key is
required. Matches and event tables are cached in Streamlit for one hour, with
bounded cache sizes. Reload after a temporary connection failure.

## Next.js frontend

`frontend/` contains the TypeScript Next.js App Router dashboard with Tailwind CSS.
It lives alongside FastAPI and the unchanged Streamlit research application.
Use Node.js 22.12+ (or a current Node LTS) and npm. From the repository root,
start FastAPI in one terminal using the command below; in a second terminal:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open **http://localhost:3000**. The default API base is
`http://127.0.0.1:8000/api/v1`; change `NEXT_PUBLIC_API_BASE_URL` in `.env.local`
and restart Next.js to override it. This public variable contains no secrets and
is embedded at build time. Requests run in the browser; use localhost:3000 because
the API's development CORS deliberately excludes other origins. Keep the frontend
and API on the same machine for these defaults. Do not publish this configuration
unchanged to a remote host.

```powershell
npm test
npm run typecheck
npm run build
npm start
```

The frontend provides competition/season, match, team and player selection;
team metric cards; shot-count comparison; a player statistics table; and an SVG
passing map. It defaults to Bundesliga 2023/24 when available. Selections remount
dependent panels to avoid stale match/team/player context. SWR caches each endpoint
by its complete path and exposes loading, retry and empty states. Zod schemas in
`frontend/lib/contracts.ts` check responses against the FastAPI contracts. Null xG
is displayed as unavailable, not zero. All analytical results and completion flags
come from Python; JavaScript only formats values and draws API-provided records.
The API does not yet expose shot coordinates or progressive passing, so this
frontend shows aggregate shots and basic passing rather than reimplementing those
analyses. Streamlit retains those research features.

Themes use semantic CSS variables in `frontend/app/globals.css`: background,
surfaces, foreground, muted text, border, accent, focus, pitch, and chart outcomes.
Dark Tactical Intelligence uses charcoal surfaces, pitch greens and restrained
yellow accents. Light Modern SaaS uses white/gray surfaces, dark type and yellow
controls with dark text. Outcome strokes adapt to both palettes. Completed passes
are solid arrows; incomplete passes are dashed, with textual legends and SVG
descriptions. Shot goals use a striped bar as well as a distinct color. Tables
provide a numeric alternative to charts. The passing map reports omitted
coordinates, and it does not classify passes itself.

`next-themes` sets `defaultTheme="system"`, `enableSystem`, and `attribute="class"`.
Light/Dark/System buttons persist the override under localStorage `fil-theme`;
System continues to follow OS preference changes. The provider's inline startup
script applies the stored/system theme before paint. Only the root `<html>`
suppresses its expected theme-attribute hydration difference; theme controls use
identical disabled SSR/initial-client markup until mounted. SVG colors use CSS
tokens directly and do not wait for JavaScript to discover the current theme.

Accessibility includes a skip link, labeled native selectors, keyboard focus
indicators, a responsive disclosure navigation, pressed-state theme buttons,
reduced-motion-aware scrolling, table row/column headers, SVG descriptions and
live loading/error states. Component tests cover theme persistence/system defaults,
server-safe markup, mobile navigation, patterned pass outcomes, missing coordinates,
API loading and retry, contract rejection and player selection. Browser-based
visual, hydration and screen-reader checks should supplement these tests.

## Sprint 1: hybrid Streamlit and FastAPI architecture

Streamlit remains the research interface and imports `src` directly. The new
FastAPI adapter also uses `StatsBombSource` and the same `src.metrics` functions;
there is no second analytics implementation or change to the Streamlit script.
The Next.js frontend now consumes this API; Streamlit continues to use Python directly.

Install/update dependencies, then run these in separate terminals from the root:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

```powershell
.venv\Scripts\python.exe -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

Streamlit uses its printed local URL (normally port 8501). FastAPI interactive
contracts are at http://127.0.0.1:8000/docs and machine-readable OpenAPI at
http://127.0.0.1:8000/openapi.json. API routes use `/api/v1`:

| GET path | Response |
| --- | --- |
| `/health` | `{"status":"ok"}`; liveness, no provider call |
| `/competitions` | Array of competition-season pairs with IDs and labels |
| `/matches?competition_id=9&season_id=281` | Array of matches, dates, team names and nullable scores |
| `/matches/{match_id}/summary` | Match ID, event count and event-observed team IDs/names, passing summaries, shot goals, shot counts, recorded xG and coverage |
| `/matches/{match_id}/teams/{team_id}/players` | Player IDs/names and the existing descriptive player statistics |
| `/matches/{match_id}/players/{player_id}/passes` | Pass IDs, nullable clock/period, completion flag and nullable `x`, `y`, `end_x`, `end_y` |

For example:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/matches?competition_id=9&season_id=281'
```

Obtain match IDs from matches, team IDs from summary, and player IDs from the team
player endpoint. All IDs must be positive integers; invalid parameters return
FastAPI's standard **422** validation response. Unknown competition-season pairs,
matches, teams or players return **404**. A known player with no passes or known
season with no matches returns `[]`. Player membership is based on named events,
not a complete lineup; a player with no recorded events cannot be looked up.

Pydantic contracts in `backend/api/schemas.py` explicitly select output fields.
Missing pandas values, NaN and positive/negative infinity serialize to JSON `null`;
unknown measurements never become fabricated zeros. Finite coordinates are those
prepared by the shared pass filter. Dates serialize as ISO strings. Extra provider
fields are excluded. Summary `shot_goals` excludes own goals and is not a final
score; xG totals cover recorded values only, accompanied by `shots_with_xg`.
The match-list scores are provider score metadata. Player xG and completion
semantics match the existing Streamlit statistics documented below.

Provider HTTP 404 maps to 404, timeouts to **504**, and other provider failures
(including rate limits) to **502**. Invalid provider response schemas also return
502. Error bodies have `{"detail":"..."}` without provider secrets or tracebacks.
The API does not add retries or authentication in this development sprint.

`backend/api/provider.py` supplies a lazy dependency with a thread-safe,
**one-hour TTL, 64-entry maximum** in-memory cache for successful catalogue and
event requests. Keys include operation and IDs. Failures are not cached. Returned
frames isolate scalar-column mutations; nested coordinate lists are read-only by
convention. A simple lock spans cache misses, trading concurrent cold loads for
avoiding duplicate downloads. Cache state is per process, cleared on restart;
multi-worker deployments do not share it. Statsbombpy may also use its own HTTP
cache. The API cache does not import or depend on Streamlit.

Development CORS permits **only `http://localhost:3000`**, GET requests and the
Accept/Content-Type headers. Credentials and wildcard origins are disabled.
`127.0.0.1:3000`, HTTPS and other ports are separate origins and are not allowed.
CORS is a browser rule, not access control. This sprint runs the API on loopback.

New modules: `main.py` configures the app, `routes.py` adapts shared functions,
`schemas.py` declares response contracts, `serialization.py` normalizes pandas
records, and `provider.py` handles requests/cache. API tests mock the data source,
exercise JSON nulls and IDs, errors, CORS, cache expiry/eviction and isolation.

Run all API and existing Streamlit/analytics tests:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## Module layout

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
