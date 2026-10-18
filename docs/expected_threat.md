# Sprint 5A: empirical expected threat (artifact schema v1)

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
