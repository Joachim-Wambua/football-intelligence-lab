# Sprint 5A: empirical expected threat (artifact schema v1)

## Sprint 5B: serving the frozen research model

**Football question:** which successful passes and observed carries move the ball
to locations assigned more value by this particular fitted surface? This is a
model-based description of buildup, not a claim about player quality or a
prediction of the next possession's outcome.

The artifact is frozen in Sprint 5B; no model is fitted, replaced or updated in
HTTP handlers. The model SHA256 remains
`7e8d1d30e10f2f89268c972d8ba9f356038475618b11b256db7d06abdf81daab`.
The active artifact has six Leverkusen training matches and two held out. **Only
26 of 192 zones contain observed shots**, even though all zones have some move
support. A converged surface can therefore still depend on very sparse goal data.

### A worked Bellman update

Suppose a zone has shot probability 0.2, move probability 0.8, and empirical
goal-given-shot probability 0.1. Successful transitions lead to B with mass 0.5
and C with mass 0.25; the remaining 0.25 of attempts lose continuation. If the
previous iteration gives V(B)=0.3 and V(C)=0.1, then:

```text
V_next = 0.2 × 0.1 + 0.8 × (0.5 × 0.3 + 0.25 × 0.1)
       = 0.02 + 0.14 = 0.16
```

Starting with all values zero, the first update is just 0.02. Later updates
propagate future shooting opportunities through successful moves. This explains
why a pass into a useful buildup zone can gain xT without ending near goal.
For a successful movement from a zone worth 0.03 to one worth 0.02, xT is -0.01;
a movement inside the same zone is a genuine zero. An unsuccessful pass or a
missing endpoint is **null**, not zero, under our destination-credit convention.

Numerical convergence only means successive Bellman updates differ by at most a
tolerance for the fitted empirical probabilities. It does not demonstrate that
those probabilities generalize, are calibrated, or are unbiased. Increasing
iterations cannot repair sparse shot zones, Leverkusen selection bias, omitted
possession-ending events or the observed-carry convention. The held-out pipeline
currently reports scoring coverage only, not a predictive validation score.

### Read-only API contracts

All endpoints are under `/api/v1`; existing endpoints and Streamlit remain intact.

| GET path | Contract |
| --- | --- |
| `/xt/model` | Actual grid/surface, per-zone shot counts, coverage, training date, coordinate convention, input hashes, convergence diagnostics and model SHA256 |
| `/matches/{match_id}/teams/{team_id}/xt/players` | Full-match, ID-grouped player totals with positive xT, signed net xT, rated counts and rated successful pass/carry counts |
| `/matches/{match_id}/teams/{team_id}/xt/actions?limit=200&offset=0` | Bounded pass/carry attempts, stable event position/ID, team/player IDs, period/clock, coordinates, success and nullable xT |

`limit` is 1–500; `offset` is nonnegative. Optional positive `player_id` filters
before pagination; absent matching actions return an empty page. `total` counts
attempts after that filter, not just rated actions. Page filters in the frontend
apply to the current page and are labeled accordingly; rankings always use all
team moves. Shots are excluded from action records; unsuccessful, malformed and
shootout moves remain inspectable with null xT. Unknown player IDs remain null in
actions and are excluded from rankings. Missing coordinates are not inferred.

`src/xt_summary.py` calls the existing `rate_actions()` for every value. It owns
aggregation in Python; TypeScript only filters/plots returned records. For
`+0.03, -0.01, 0, null`, positive xT is 0.03, net xT is 0.02 and rated count is 3.
Entirely unrated players have null totals. Rated pass/carry counts include only
successful moves with defined valuation. Rankings sort positive xT descending,
then net xT descending, then stable player ID; they are not normalized per 90.

`backend/api/xt_model.py` validates surface shape/range, positive grid dimensions,
finite shot/goal support, convergence diagnostics, disjoint partitions and the
exact `StatsBomb 120x80 attacking right` contract. Provider events come from the
existing StatsBomb adapter and are never flipped by team or half. Custom sources
need a separately verified normalization adapter. Malformed coordinates yield
null valuations through the shared research engine. No client direction override
is accepted. The model is cached per process until restart; failed loads are not
cached. After an intentional artifact deployment restart the API. Request
parameters cannot select another file. Every response includes the same model
hash, and the frontend refuses to compare mismatching versions.

Missing/corrupt/incompatible artifacts return safe **503** responses without local
paths. Existing provider errors retain 404/502/504 mappings. Invalid parameters
return 422. `/health` remains process liveness, not model/provider readiness.

### Dashboard and verification

The Expected Threat panel renders the actual 16×12 fitted grid. Hover, click or
keyboard-focus a zone to inspect its value and observed shot count; Enter/Space
selects it and Escape clears selection. A text table lists all 192 zones. Overlay
passes are solid and carries dashed, with destination dots; signed values and
unrated events are available in a table, not communicated by color alone.
Light/Dark/System controls and persistence are unchanged. Colors use theme tokens;
color scaling is presentation only, not additional statistical smoothing.

The panel explicitly labels the model **Experimental xT**, displays provenance
and sparse coverage, and warns that it is not calibrated, broadly representative
or suitable for definitive scouting assessments. The grid can be inspected even
when provider requests fail. Overlays are opt-in to avoid an unnecessary event
download. Model failure stays within this panel; other research views still work.

```powershell
.venv\Scripts\python.exe -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
# In another terminal:
cd frontend
npm ci
npm run dev
```

```powershell
# Repository root:
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm test
npm run typecheck
npm run build
```

Tests use small, readable signed-value examples and the actual checked-in surface.
They verify null-versus-zero semantics, grouping by IDs, pagination, model
validation/caching, provider failures, theme behavior, filtering and keyboard/text
alternatives. These checks verify implementation and accessibility semantics;
they are not football-model predictive validation or a screen-reader/browser audit.

## Research engine and mathematical definition

The grid follows [Karun Singh's expected-threat formulation](https://karun.in/blog/expected-threat.html).
For zone i, let S, M, G be eligible shots, move attempts, and shot goals.
Let C(i,j) count successful moves with valid destination j.

    p_shot(i) = S(i)/(S(i)+M(i))
    p_move(i) = M(i)/(S(i)+M(i))
    p_goal_given_shot(i) = G(i)/S(i)
    T(i,j) = C(i,j)/M(i)
    V_next(i) = p_shot(i)*p_goal_given_shot(i) + p_move(i)*sum_j T(i,j)*V(i)

All zero denominators return zero. T is deliberately substochastic: its row sum
is the observed usable successful-move fraction, not one. This incorporates
failed passes as zero continuation rather than conditioning them away. Iteration
starts at zero, yielding the least nonnegative fixed point. A closed move-only
cycle stays zero; no goal evidence is invented. Stop when maximum absolute change
is at most tolerance; iteration exhaustion raises and prevents artifact export.
The artifact records the complete residual series. It uses empirical goal counts,
not StatsBomb xG. This is an extension of the successful-move formulation.

## Data and outcomes

Inputs use flattened StatsBomb fields as in src/datasets.py; the research CLI
normalizes raw open-data JSON into that schema. See the [provider repository and
specifications](https://github.com/statsbomb/open-data). No existing loader,
metrics, progression code, API, or frontend behavior is changed.

* StatsBomb provides event coordinates in a 120 by 80 attacking-right frame.
  The pipeline explicitly declares that provider contract. Do not flip teams or
  second halves. The low-level functions require right/left direction; left
  rotates both axes by 180 degrees. Unknown direction raises. This validates
  bounds and direction declarations, not physical orientation from tracking.
  Custom local exports must have their coordinate convention verified upstream;
  do not infer direction from a small sample of shots or home/away identity.
  The CLI's `--direction left` option is only for a separately verified,
  uniformly leftward export; do not apply it to standard StatsBomb open data.
  Mixed-direction exports must first normalize each team's period upstream.
* Missing/null pass_outcome means completed, consistent with existing metrics.
  Any non-null outcome (including Unknown, Out, Incomplete, offside) receives no
  successful destination credit. Incomplete attempts with valid starts remain
  in move denominators. A missing outcome column is accepted under the provider
  contract; a lossy export that removed outcomes is not eligible research data.
  Malformed non-scalar outcomes are ineligible, rather than being treated as
  completed. Unknown shot outcomes are also ineligible.
* Carry uses carry_end_location exclusively. StatsBomb carries are observed
  movement segments, assumed successful; they are not attempted dribbles and do
  not provide a failed-carry denominator. No endpoint is borrowed from another
  event. Invalid endpoints have zero continuation in fitting and null valuation.
* Shots need a recognized outcome and valid start. Only Goal is a goal. Shootouts
  (period 5) are excluded. Normal/extra-time penalties and set pieces are pooled.
  Invalid starts and unknown shot outcomes are retained in extraction diagnostics
  but excluded from fitting. Own-goal events are outside this shot model.
* Zone boundaries are half-open internally; x=120 and y=80 enter the last cells.
  Malformed, nonfinite, boolean, and out-of-bounds coordinates are undefined.

Valuation returns a copy with nullable Float64 xT. Valid successful passes and
carries get V(end)-V(start), preserving negative values and genuine zero changes.
Shots, failed passes, and invalid geometry remain null. Unobserved zones have an
explicit zero fallback, not a calibrated estimate; counts identify those zones.
A valid action involving such a zone uses that documented fallback.

## Offline reproduction

Install requirements.txt. Obtain a local StatsBomb open-data checkout; keep raw
events outside Git. Pin its commit for repeated experiments; artifacts additionally
record SHA256 for the exact match manifest and selected event files, match IDs,
dates, counts, competition-season, grid, parameters and UTC training timestamp.
The timestamp intentionally changes on retraining; estimates are deterministic
for identical inputs. No network request or fit occurs at import or in the API.

    python -m src.xt_research path/to/open-data/data --competition 9 --season 281 --limit 8 --held-out 2 --nx 16 --ny 12 --output artifacts/xt-v1.json --report research/xt
    python -m pytest -q

In this recovered workspace, `path/to/open-data/data` can be replaced by
`research/xt-data` (the already downloaded, gitignored eight-match subset).
For a fresh checkout, download a pinned copy of StatsBomb open-data separately
and use its `data/` directory. Optionally pass `--source-revision <commit>`;
the manifest/event hashes remain the authoritative exact-input identifiers.
The local subset and a full checkout select the same first eight chronological
available fixtures, provided their files/hashes match. A missing early file can
change that selection: always compare the recorded match IDs and hashes.

The CLI selects available matches with local event files, sorted by date then ID.
It reserves the final two selected matches; at least two training matches are
required. Missing files are excluded with published/local/selected counts recorded;
malformed or apparently incomplete selected files fail loudly. Both regulation
Half End markers are required as a basic integrity check, not proof of complete
collection. Selection never
claims that a competition or season is complete. For exact reproduction supply
the same local files (their hashes must match the artifact). The checked-in model
is a small eight-match Bundesliga 2023/24 experiment, not a full-season model.

The report writes a heatmap, convergence plot and first 30 eligible held-out pass
valuations in source order. Held-out counts describe coverage only: there is no
claimed possession-goal calibration, predictive benchmark, or player ranking.
Inspect the artifact metadata and diagnostics before interpreting its surface.

### Recovered experiment coverage

`artifacts/xt-v1.json` is a 16 × 12 research artifact, fitted on October 18, 2026
(UTC timestamp recorded in the artifact). The manifest publishes 34 Leverkusen
fixtures; only eight event files are locally present. This is neither the full
306-match Bundesliga schedule nor a complete Leverkusen-season training run.

- Training (August 19–September 30, 2023): IDs `3895052`, `3895060`, `3895067`,
  `3895074`, `3895086`, `3895095`.
- Held out (October 8 and 21, 2023): IDs `3895107`, `3895113`.
- Training has 13,070 eligible actions: 159 shots (25 goals), 7,089 pass attempts
  and 5,822 carries. The fitted grid has no wholly unobserved start zones, but
  shot support remains sparse and many zones have no shots.
- Iteration converged in 167 updates at a final maximum change of about
  `9.19e-11` (tolerance `1e-10`). This is numerical convergence, not calibration.
- The held-out files contain 8,267 events, 4,354 extracted actions and 3,962
  successful, valid moves with defined valuation. Held-out outcomes never enter
  shot, goal or transition estimates. These counts measure coverage only.

The JSON is approximately 39 KB and includes the surface, grid/fit parameters,
version, UTC timestamp, provenance, exact input hashes, partition IDs, per-match
counts and teams, probability/count arrays, transition row sums and convergence
history. It omits raw events and the dense transition matrix; neither is required
to rate actions. `load_model` and `save_model` validate the surface and version,
and serialization forbids NaN/Infinity. Full fitted probability matrices can be
recomputed from the recorded training inputs; this is a scoring artifact, not
a complete fit checkpoint.

## Limitations

Location alone is the Markov state; actions are pooled across teams, score,
pressure, game time and play patterns. Shots terminate even if rebounds occur;
failed moves terminate even if possession is recovered. Other possession-ending
actions are omitted, making this an action-conditioned simplified possession
model, not a calibrated probability of scoring in an actual possession. The
observed carry convention can inflate continuation relative to failed dribbles.
No discount, pseudocounts, interpolation, spatial smoothing or provider xG prior
is used. Sparse zones and the zero fallback can materially distort differences.
The small artifact demonstrates research plumbing; retrain with broader verified
coverage before football conclusions. Data remains subject to StatsBomb's terms;
credit StatsBomb and follow its attribution requirements when publishing research.
