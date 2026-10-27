# Player Comparison (Sprint 8B)

## Question and comparison scope

What did two identified players contribute in the same selected files, and how do
their qualified rates differ after making exposure visible? This is a descriptive
comparison, not a scouting verdict or a league-wide ranking. Percentile radars
remain deferred to the separately validated Sprint 8C.

Open `/players`, apply one to five fixtures, and choose **Compare players**. Select
two distinct numeric provider IDs, optionally searching each list. Both players
come from **one catalogue response** with the same competition, season, team,
requested match IDs, included IDs and model artifact. Duplicate names never merge.
Positions show all provider-supported roles; no primary role is inferred. The
header distinguishes requested files, included files, and any failures. Each
player shows appearances, unknown appearances, verified/known minutes, minutes
coverage, per90 denominator match IDs, position histories' role labels, xG shot
coverage and xT rated/attempted moves.

Same files do not imply equal participation, roles, opposition exposure or game
state. Totals reflect actual opportunities; per90 only normalizes recorded elapsed
pitch time. It does not remove selection bias or make players interchangeable.
Minutes follow the [audited Sprint 8A methodology](player_intelligence.md), including
added time and excluding intervals and shootouts.

## Python-owned values and qualification

The existing catalogue already supplies both player aggregates; selecting a second
identity causes **no additional profile/provider request**. The shared
`PlayerCollectionService` still caps requests at 1–5 matches, caches raw files,
and shares eight prepared collections for 15 minutes. No pair-specific endpoint,
season scan, mathematical TypeScript metric or model fit is introduced.

The only additive API field is `PlayerAggregate.comparison_evidence`, available in
both existing catalogue/profile responses and validated by Pydantic/Zod. Each
metric provides its definition, kind, covered total, qualified per90, chart total,
coverage counts, status and explanation. `src/player_comparison.py` qualifies the
existing Python aggregate; it does not recalculate counts or invent a score.
Existing Sprint 8A totals/per90 fields retain their semantics.

| Evidence | Numeric totals | Bars and comparison per90 |
| --- | --- | --- |
| Observed counts, all selected files available | Recorded counts, including genuine zero | Bar retains zero; rate needs complete valid positive minutes |
| Some included minutes unknown or zero | Recorded counts remain visible | Totals can be plotted; rates are null where exposure is unsupported |
| Selected-file failure | Clearly labelled included-subset totals | Withheld, since the requested sample is incomplete |
| Incomplete passing geometry | Covered completed-progressive count, with valid/all attempts | Withheld for that geometric metric |
| Partial provider xG | Covered-only sum with covered/all shots | Withheld; missing probabilities never become zero |
| Any unrated xT attempt | Rated-move-only signed sum and rated/all move coverage | Withheld for xT, without an arbitrary minimum-coverage cutoff |
| Complete recorded xG/xT coverage | Provider/frozen-model estimate, not observed output | Qualified bars/rates; model limitations still apply |
| No covered estimate | Unavailable | No bar or zero marker |

The strict xT rule also includes intentionally unrated unsuccessful/ineligible
moves. It does **not** claim all attempted moves should be rated by this model.
A withheld xT bar is not zero value; a fully rated bar is not a complete account
of player ability. The frozen model's ID, training/held-out counts, shot-zone
support and sparse Leverkusen sample limitations remain visible.

Per90 remains `90 * sum(count) / sum(valid elapsed minutes)` over the same numerator
files. Example: two shots in 30 minutes plus one in 90 gives 2.25 shots/90, not
mean(6, 1) = 3.5. Unknown exposure or missing selected files suppress pooled rates;
partial xG and unrated xT additionally suppress comparison rates. The original
profile's rated-output xT rate remains inspectable with its existing qualification;
comparison does not silently reinterpret it as full-output xT.

Bar widths are SVG presentation only. Each metric uses a common zero-centred scale
for the pair, with negative values extending left. Different metrics have separate
units/scales and are never combined. Zero has a baseline point; null has explicit
unavailable text and no marker. Small nonzero deltas that would round to zero use
scientific notation. Solid/outlined bars, A/B legends, provider IDs, focusable
labels and numeric tables avoid color-only interpretation. Themes use existing
tokens; no animation is required.

## URL restoration

Player contribution links target the actual Match Intelligence route with
`competition_id`, `season_id`, `match_id` and `team_id`.
`readMatchSelection` validates positive safe integer syntax, rejects repeated
parameters and applies a hierarchy: match requires competition/season; team
requires match. The client then validates membership against the loaded catalogue
and match summary. An unavailable parent drops its child IDs before choosing
normal defaults; a valid empty season stays empty. Unknown teams fall back within
the verified match. Shape-valid summaries for another match are rejected.

A subsequent URL change remounts selection state, including distinct invalid URLs
that resolve to the same defaults. Manual competition/match changes stop reusing
old URL children. In-workspace section links preserve the current query parameters.
Keyed requests isolate late responses. This follows
Next.js's [page searchParams model](https://nextjs.org/docs/app/api-reference/file-conventions/page):
updated route values arrive as new page props, rather than only initial state.
Tests render the actual destination page, including following a contribution link;
they assert selected competition/season/match/team and the requested team endpoint,
not just link text.

## Verification and automation

```powershell
.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_cache/sprint8b
cd frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

Python tests cover pooled denominators, partial/missing estimates, signed/zero xT,
invalid/zero minutes, stable IDs, context rejection and shared provider-cache reuse.
Frontend tests cover actual route restoration/defaults, repeated navigation,
late responses, distinct selection/search, totals/per90, nulls, signed bars, keyboard
focus, table alternatives, themes and no second-player fetch.

`.github/workflows/checks.yml` runs pytest and frontend tests/typecheck/build on PRs
and main pushes, with read-only repository permission, official actions pinned to
verified immutable SHAs, Python 3.12, Node 22, dependency caches and timeouts. No
secrets, provider downloads, deployment or model fitting are part of those checks.
The typecheck command generates Next route types before `tsc` so it also works on
a clean checkout. The workflow follows the official
[setup-node](https://github.com/actions/setup-node) and
[setup-python](https://github.com/actions/setup-python) guidance.
