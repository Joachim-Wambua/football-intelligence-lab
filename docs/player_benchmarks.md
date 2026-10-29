# Player benchmarking feasibility — Sprint 8C.1

## Decision and football question

Can an identified player be compared with a position-aware reference population
without presenting missing exposure, selected matches or experimental estimates
as league-wide ability? **The foundation is implementable; a general radar release
is not justified by the deeply audited sample under the default policy.**

This audit inspected StatsBomb open data at revision
`4b73468fc5b0f1950f9f66fada70ad3a4f9327cb` on 29 October 2026.
[Catalogue evidence](benchmark_catalogue.json) inventories all 80 published
competition-season pairs. [Content/feasibility evidence](benchmark_feasibility.json)
records the fully downloaded 2023 Women's World Cup sample, source byte hashes,
match IDs, minutes-status counts, dependency versions, implementation hashes and
threshold sensitivity. These are two distinct levels of evidence.

Data source: **StatsBomb**.

![StatsBomb](https://raw.githubusercontent.com/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/img/SB%20-%20Icon%20Lockup%20-%20Colour%20positive.png)

## Available data and limits of verification

Every published catalogue was downloaded at the same pinned revision. The
nontruncated recursive Git tree was checked for each listed event and lineup
path. No listed match was missing either path. This establishes published file
presence, **not** content quality, a complete real-world season, or complete
player participation. Uninspected player counts are explicitly null in the
catalogue report; lineup completeness is marked `not_content_audited`.

Promising multi-team candidates include:

| Competition-season | Provider IDs | Available matches | Teams | Evidence |
| --- | --- | ---: | ---: | --- |
| FA Women's Super League 2023/24 | 37 / 281 | 132 | 12 | Catalogue + file presence |
| Frauen Bundesliga 2023/24 | 135 / 281 | 132 | 12 | Catalogue + file presence |
| Liga F 2023/24 | 182 / 281 | 240 | 16 | Catalogue + file presence |
| Premier League 2015/16 | 2 / 27 | 380 | 20 | Catalogue + file presence |
| Women's World Cup 2023 | 72 / 107 | 64 | 32 | All events + lineups inspected |

The machine-readable inventory is authoritative for the provider IDs and counts.
Do not interpret the match totals as independent fixture-schedule verification.
The existing Leverkusen release is a selected-team sample and cannot represent
all Bundesliga players. The tournament was chosen for a bounded, multi-team
end-to-end content audit, not as a surrogate domestic league.

All 64 published tournament event/lineup pairs were downloaded and parsed. Each
lineup contained the two expected teams. There were 736 unique squad player IDs
(736 player/team contexts), 32 teams, and no missing files. Across 2,920 squad
records: 1,778 verified appearances, 1,018 verified unused substitutes, and 124
unsupported temporary-absence records. The last category affects 105 pooled
player contexts: those players retain counts and known partial minutes but have
null pooled minutes/rates. File completeness does not certify minute completeness.

## Offline reference preparation and identity

`src/benchmark_prepare.py` reads local provider JSON only. It uses statsbombpy's
existing flattening convention and calls `match_players` and `aggregate_player`,
therefore reusing the [audited elapsed-time logic](player_intelligence.md) and
[metric coverage qualification](player_comparison.md). It never calls a provider,
loads/fits xT, or runs inside an HTTP request. Existing API routes, caches and
frontend flows are unchanged.

Keys are provider player ID + competition + season + team. Display aliases do not
merge people. Transfers retain separate team stints; a future population of these
contexts can weight a transferred identity twice, so it must be labelled as a
player/team population. No cross-team identity pooling is performed. Each row
retains match IDs, original position histories, counts, aggregate elapsed minutes,
partial known minutes, covered numerators and qualified comparison per90.

Counts and minutes pool over the same available appearances. A complete squad
omitting a player contributes no appearances; it is not evidence that an unseen
player with a missing lineup did not play. Any missing selected event/lineup file
conservatively suppresses all dataset rates. Missing lifecycle exposure in any
included player record suppresses that player's pooled rates. Corrupt input fails
the build instead of silently disappearing. Empty/duplicate match catalogues fail.

Example: 2 shots in 30 minutes plus 1 in 90 gives
`90 * (2 + 1) / (30 + 90) = 2.25 shots/90`. Averaging the individual rates gives
`(6 + 1) / 2 = 3.5`, which overweights the short appearance. Unknown minutes do not
become 90, zero, or a smaller quietly selected denominator.

The source manifest hashes decompressed original JSON bytes, so `.json` and
`.json.gz` inputs yield the same build. Dataset version hashes source identities,
missing paths, policy, dependency versions and implementation hashes. JSON output
is deterministically ordered, disallows NaN, and contains no wall-clock build date.
Keep the full reference output, compressed raw files and temporary artifacts in
ignored `research/benchmarks/`. Only audit manifests and analysis summaries enter Git.

## Position cohorts and policy sensitivity

The experimental `unanimous-broad-group-v1` policy uses actual lineup
`position_id` histories: goalkeeper {1}; centre back {3,4,5}; full back/wing back
{2,6,7,8}; midfield {9–16,18,19,20}; wide forward {17,21}; striker {22–25}.
All appeared-match spells must map to one group. An unknown ID, missing history,
unknown participation, or cross-group change leaves the context unassigned.
Unused substitutes do not create a role. This is a conservative exploratory
taxonomy, not a validated equivalence of tactical roles or an inferred primary
position. It does not subtract nominal lineup clocks to estimate role minutes.

Of 736 contexts, 366 are unassigned: 117 never appeared and 249 appeared with
mixed/unsupported histories. Role changes remain visible in the local reference
output. Requiring unanimous histories selects stable roles and is itself biased.

Eligible contexts require a role, complete positive pooled exposure and the
specified minimum elapsed minutes:

| Role | 180 minutes | 450 minutes (default) | 900 minutes |
| --- | ---: | ---: | ---: |
| Goalkeeper | 32 | 7 | 0 |
| Centre back | 35 | 6 | 0 |
| Full back | 27 | 4 | 0 |
| Midfield | 58 | 11 | 0 |
| Wide forward | 6 | 1 | 0 |
| Striker | 11 | 2 | 0 |

The default minimum cohort size is 20 **qualified finite metric observations**,
not merely 20 roster members. No default cohort qualifies. At 450 minutes and a
size policy of 10, midfield qualifies (10 xG values; 11 for the other metrics).
At 180 minutes several roles pass 20 observations. These alternatives are
documented sensitivity checks, not reasons to lower thresholds until a radar
looks populated. Neither 450 minutes nor n=20 is a statistical guarantee.

Tournament advancement increases possible exposure: a minimum of 450 minutes
selects players from teams that progressed, plus particular starters. Per90 cannot
remove opponent strength, tactical opportunity, game state, knockout survival or
the missing-minute and stable-role selection effects. Pooling unrelated leagues,
seasons or genders merely to enlarge n is not a defensible fix.

## Metric coverage and percentile mathematics

Across all roster contexts, before role/minute thresholds, 514 have qualified
per90 for pass attempts, completed passes, completed progressive passes, shots,
shot goals, successful dribbles and successful interceptions. Only 302 have
qualified provider xG per90. All default eligible players have full recorded shot
xG coverage where shots exist; no-shot xG remains unavailable under the existing
contract. Progressive passing additionally requires complete recorded geometry.
The summary reports metric-specific sample sizes, not a single misleading n.

xG remains a provider estimate. Partial shot probabilities retain their covered
sum but do not enter percentile references. All-missing/no-shot xG is null.
Experimental xT is excluded from `BENCHMARK_METRICS`; no model is fitted or loaded
by the builder. The existing sparse xT validation does not justify benchmark radars.

`empirical_percentile` accepts an explicit reference sequence of eligible finite
rates, target value/exposure, minimum minutes/samples, and direction. Reference
membership is caller-owned and must represent the documented context; it is not
inferred from names. Include the target when it belongs to that population.
The exact-tie mid-distribution policy is:

`P(v) = 100 * (number below v + 0.5 * number equal to v) / n`.

For `[1, 2, 2, 4]`, percentiles are `[12.5, 50, 50, 87.5]`. Equal observations
share the tie mass. Constant populations give 50, not evidence of elite/poor
performance. Lower-is-better reverses this to `100 - P`; the current volume
metrics' higher direction is a descriptive ordering, not a claim that more is
always better football. Exact equality defines ties; values are not rounded first.
Nonfinite/missing reference values are excluded and sample size is reported.
Missing targets, low exposure and insufficient finite samples return null with a
status, never zero. These are empirical ranks, not confidence intervals or causal
ability probabilities. No real player percentiles are published in this sprint.

## Contracts and Sprint 8C.2 recommendation

Standalone Pydantic and Zod `benchmark-v1` contracts reserve explicit dataset
version, competition/season/team/player IDs, role, reference player/team pairs,
match IDs, thresholds, direction, tie policy, per-metric n, nullable rank/status
and limitations. Availability checks prevent an unavailable percentile from
becoming a zero marker. There is no benchmark endpoint or radar UI yet.

Proceed with a **domestic competition content audit before a radar sprint**:
use the 132-match WSL 2023/24 catalogue as a realistic next reference candidate,
verify fixture coverage independently, inspect all lineup/event contents, quantify
temporary-absence exclusions, and validate role grouping with football review.
The same offline builder accepts any collected competition-season. Keep tournament
ranks labelled as exploratory tournament ranks if separately pursued; they cannot
benchmark Leverkusen against Bundesliga peers. If domestic exposure remains too
incomplete, retain the existing selected-match descriptive comparison while
seeking a suitable licensed reference dataset. No evidence here establishes that
all accessible domestic candidates are unsuitable; their contents remain unaudited.

## Reproduce and verify

From repository root with the existing Python requirements installed:

```powershell
.venv/Scripts/python.exe tools/collect_benchmarks.py --cache research/benchmarks/raw --output docs/benchmark_catalogue.json --revision 4b73468fc5b0f1950f9f66fada70ad3a4f9327cb
.venv/Scripts/python.exe -m src.benchmark_prepare research/benchmarks/raw --competition 72 --season 107 --output research/benchmarks/reference.json --summary-output docs/benchmark_feasibility.json
.venv/Scripts/python.exe -m pytest -q
cd frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

The collector is an explicit network operation; the builder/tests are offline.
It retries transient host failures instead of reporting them as absent data.
Re-run the builder to compare byte-identical outputs with identical inputs/code/
dependencies. Pass `--minimum-minutes` and `--minimum-samples` for explicit policy
experiments. Unit tests cover raw/compressed equivalence, determinism, pooled
exposure, duplicate names, separate team stints, missing files/minutes/xG, role
changes, ranks/ties/direction, invalid policies and contract null semantics.

Validation for this sprint: 224 Python tests and 81 frontend tests passed;
typecheck and the Next.js production build passed. The final targeted Python
boundary/integration rerun passed all 20 tests after the transfer example was
refined. Two actual 64-match builds agreed on every player aggregate, position
history, cohort and match audit record; compressed/uncompressed byte-equivalence
and fully identical builds are also covered by offline integration tests. The
existing GitHub Actions workflow is unchanged and runs both suites on the PR.

## Provider terms and attribution

The pinned [README](https://github.com/statsbomb/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/README.md)
requires naming StatsBomb and using its logo when sharing analysis. The pinned
[Public Data User Agreement](https://github.com/statsbomb/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/LICENSE.pdf)
(last updated 8 September 2023) describes research use, restricts redistribution
of source data and commercial exploitation of data/derived analysis, requires logo
accreditation, requests user registration, and provides no completeness warranty.
The report records hashes for both documents. Openly downloadable does not mean
unrestricted redistribution: download raw inputs directly from the provider and
keep them outside Git. Confirm appropriate provider permission before commercial
use. This sprint publishes source manifests and analytical audit results only.
