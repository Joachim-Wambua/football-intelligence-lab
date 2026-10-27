# Player Intelligence foundation: evidence, minutes and sample bias

## Football question and source audit

This module asks what an identified player contributed in **explicitly selected
matches**, how much recorded pitch time supports those counts, and which rates
can be normalized without inventing exposure. It does not define a league-wide
reference population. Sprint 8B adds descriptive [two-player comparison](player_comparison.md). Percentile
radars require separate Sprint 8C validation; ratings, physical attributes and
inferred primary-position benchmarks are not introduced.

On 25 October 2026 the audit downloaded actual public JSON from the
[StatsBomb repository](https://github.com/statsbomb/open-data), rather than relying
on invented examples. The small [audit manifest](player_audit.json) records the
SHA256 of every event/lineup file, period lengths and **every provider player ID**
classified as a verified appearance, verified unused substitute or null-minute
case. Raw files stay outside version control. Byte hashes identify the inspected
revision even if upstream `master` later changes.

| Fixture | Source context | Team | Verified played / unused / null |
| --- | --- | --- | --- |
| 3895052, 2023-08-19, Leverkusen–Leipzig | 9 / 281 | Leverkusen 904 | 14 / 5 / 1 |
| same | same | Leipzig 182 | 16 / 4 / 0 |
| 3895060, 2023-08-26, Gladbach–Leverkusen | 9 / 281 | Gladbach 185 | 16 / 4 / 0 |
| same | same | Leverkusen 904 | 16 / 4 / 0 |
| 8656, 2018-07-11, Croatia–England, extra time | 43 / 3 | Croatia 785 | 15 / 7 / 0 |
| same | same | England 768 | 13 / 8 / 2 |
| 7541, 2018-06-19, Colombia–Japan | 43 / 3 | Colombia 769 | 14 / 9 / 0 |
| same | same | Japan 778 | 14 / 9 / 0 |

There are 171 squad records: 118 verified played, 50 verified unused, and three
null-minute appearances with explicit participation but unsupported temporary
absences. Null cases are Leverkusen **32712**, England **3205** and **3308**.
This is evidence about these files, not a certification of every StatsBomb match.
The dismissal example is Colombia **5685**, Carlos Sánchez: red card at first-half
`00:02:48.560`, yielding `168.560 / 60 = 2.809333...` elapsed pitch minutes.

Primary records include [Leverkusen lineups](https://github.com/statsbomb/open-data/blob/master/data/lineups/3895052.json),
[the extra-time events](https://github.com/statsbomb/open-data/blob/master/data/events/8656.json),
and [the dismissal events](https://github.com/statsbomb/open-data/blob/master/data/events/7541.json).
The [provider event specification](https://github.com/statsbomb/open-data/blob/master/doc/StatsBomb%20Open%20Data%20Specification%20v1.1.pdf)
describes Starting XI, Tactical Shift, substitutions, temporary Player Off/On,
card types and Half Start/Half End. The audit also inspected the installed
statsbombpy flattener: `substitution_replacement_id` is preserved; names are not
needed to connect an outgoing and incoming player.

### What the actual source contains

- Lineup files contain complete squad IDs/names, including unused substitutes;
  nested `positions` record role changes, start/end periods, times and reasons.
  A squad entry alone is not an appearance. Empty position history is common for
  unused substitutes; it is not a license to assume everybody played 90 minutes.
- Event Starting XI `tactics.lineup` identifies eleven starters by numeric ID.
  Substitutions identify the outgoing player and numeric replacement ID.
- Red and second-yellow dismissals can occur in `foul_committed_card` or
  `bad_behaviour_card`. Bench cards do not remove a pitch player. Lineup card/
  position evidence can expose a missing dismissal or substitution event.
- Events contain periods 1–2, and 3–4 for extra time; period 5 is a shootout.
  Timestamps are **period-relative**, while lineup position clocks use nominal
  match-clock offsets. Position clocks are preserved, not subtracted naively.
- Both teams can supply a Half End. England–Croatia has small differences, up to
  0.280 seconds. The implementation accepts agreement within one second and uses
  the maximum recorded endpoint. Larger disagreement remains unverified.
- Temporary Off/On and off-camera returns exist in these real files. Their
  exposure policy is intentionally unsupported here and gives null for that
  player, without invalidating everyone else's reliable minutes.

## Playing-time algorithm and limitations

`src/playing_time.py` creates a cumulative **elapsed pitch-time** axis. For an
event in period p, add its period-relative timestamp to the sum of actual earlier
period lengths. This excludes the halftime/extra-time intervals and includes
recorded added time. It is neither ball-in-play time nor the common capped
90/120-minute reporting convention. Other sites may therefore report different
minutes. Every response describes this denominator explicitly.

Require complete Half Start/Half End records for periods 1 and 2, and both 3 and
4 if extra time is present. Reject short, missing or conflicting period endings,
invalid clocks, invalid/duplicated roster IDs and incomplete Starting XI. Initialize
starters at zero; close/open active intervals at ID-verified substitution events;
close an active player on an explicit dismissal; close remaining intervals at the
final eligible whistle. Never extrapolate the match ending from the last touch.
An on-ball event outside a verified interval exposes conflict instead of defining
an interval. Explicit Starting XI/substitution IDs and recorded on-field actions can
confirm an appearance even when a missing roster prevents reliable minutes; no-touch
replacements remain in the catalogue with unknown exposure. Position history can expose an otherwise invisible no-touch substitute.

For example, with a 47-minute first half and a 49-minute second half, a halftime
substitute has 49 elapsed minutes and a full-match player has 96. A substitute
entering at second-half 48:00 has one minute. Extra time uses the actual lengths
of both additional periods; shootouts add neither playing time nor contributions.
A verified unused squad player has zero and `appeared=false`. Unknown exposure has
null with `minutes_status` and `minutes_provenance`. A player omitted from a complete
team squad has `not_in_squad`, zero minutes and no appearance; absent lineups cannot
establish that zero. The event API is assumed to be a complete provider match file.
Missing or incorrectly collected source records can still limit completeness;
"verified" always means verified under these documented source checks.

## Counts, estimates and normalization

`src/player_analytics.py` groups **only by provider player ID**, preserving display
aliases and provider position histories. It reuses `descriptive_statistics`,
`progressive_passes`, `valued_moves` and `player_xt_summary`; no football calculations
are duplicated in TypeScript. Existing Match Intelligence retains its all-period
contracts, while this player module explicitly excludes shootouts so counts align
with its minutes denominator. Unknown-period events cannot certify minutes.

Observed counts cover pass attempts/completions, completed progressive passes,
shots/shot goals, successful dribbles/interceptions and valid passing geometry.
xG is a **provider estimate**, with covered shots / all shots; a partial sum remains
partial and all missing stays null. xT is the existing **experimental frozen
estimate**, with model ID, training/held-out coverage and rated/attempted move counts.
Unrated actions never become measured zero value. No request fits a model.

Per90 = `90 * sum(metric) / sum(elapsed minutes)` for the same included records.
Two shots in 30 minutes and one in 90 minutes give `90 * 3 / 120 = 2.25`, not the
mean of 6 and 1. Rates are null for zero/invalid minutes. If **any** included
player-match exposure is unknown, all aggregate rates are null; `known_minutes`
still shows its explicitly partial sum and `minutes_covered_matches` shows support.
Failed selected files also suppress pooled rates rather than quietly dropping
unknown numerator/exposure. Per-match rates remain available when individually
supported. xG per90 is additionally null when any shot probability is missing.
Coverage is not a confidence interval and per90 does not remove selection, game-state,
role, opponent-strength or small-sample bias. No minimum-minute scouting claim is made.

## API, source boundary and bounded work

`DatasetSource` now includes `lineups(match_id)`. `StatsBombSource` preserves raw
nested positions/cards through a normalized squad table. `LocalDatasetSource`
optionally reads `lineups/<match_id>.json`; absent files mean unavailable. Rows
require `team_id`, `team`, `player_id`, `player`, `positions`, `cards`. Other providers
must adapt their own clocks, lifecycle and outcome conventions first.

Versioned endpoints:

```text
GET /api/v1/player-intelligence/players
GET /api/v1/player-intelligence/players/{player_id}
?competition_id=9&season_id=281&team_id=904&match_ids=3895052&match_ids=3895060
```

Every request must explicitly select **one to five distinct positive match IDs**.
Unknown catalogue membership/context is 404; invalid IDs/selection length/duplicates
are 422. Responses are Pydantic validated. A missing selected event file or team
absence appears in `failed_matches`, while missing lineups qualify minutes without
hiding recorded contributions. If no selected team match is available, return 404.
Unavailable xT leaves observed data usable. Context, definitions, model ID, sample
IDs and per-match coverage accompany each profile; catalogue includes unused players.

Cold preparation fetches at most five event files plus five lineup files. The
existing 64-entry, one-hour raw provider cache now includes lineups. An eight-entry,
15-minute aggregation cache shares all prepared identities/profiles for a canonical
selection; its key includes provider, context and model ID. A lock prevents duplicate
cold aggregation and returned snapshots are copied. Partial collections are also
cached for that interval. Workers cache independently; source files are not an atomic
transaction. Expensive training remains an offline research operation.

## Run and verify

Start the existing FastAPI and Next.js servers as described in the README; open
`/players` or the **Player Intelligence** navigation entry. Choose competition/season,
an anchor fixture to identify a team, then apply one to five team fixtures. The
frontend filters candidate fixture labels for convenience; Python verifies actual
team IDs. Search names/IDs, select a provider identity, inspect numerator/denominator
coverage and expand minutes/position evidence. Match links restore the correct
competition, season, match and team in Match Intelligence. Light/Dark/System and
existing Match Intelligence/report features remain available.

```powershell
.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_cache/sprint8a-full
cd frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

To reproduce the audit using a local checkout of the public repository:

```powershell
.venv\Scripts\python.exe -m src.player_audit path/to/open-data/data --output docs/player_audit.json
```

The committed audit uses the recorded inspection date 2026-10-25; future runs use
current UTC date by default or accept `--audited-on`. Unit/API tests are offline and
synthetic; the real-file audit is separate evidence, not an upstream availability
check performed during every test run. Tests teach exact lifecycle boundaries,
late/halftime substitutions, benches, dismissals, extra time, null xG, duplicate
names, invalid minutes, matching per90 exposure, caching and identity-safe navigation.

### Real collection smoke validation

In addition to the audit, the two downloaded Leverkusen fixtures 3895052 and
3895060 were passed through the actual player collection service with the existing
frozen xT artifact, then validated with `PlayerCatalogue` and `PlayerProfile`.
The union contained **21 provider identities**. Granit Xhaka (3500) had
**198.689283 elapsed minutes** across both files. Jeremie Frimpong (32712) had
**null pooled minutes/per-90**, with **75.451617 known minutes** in the second file
and `temporary_absence_unsupported` in the first. This demonstrates the intended
missingness boundary on real inputs, not just synthetic tests. Raw downloads were
kept in the ignored audit cache; no live network requests occur in unit tests.
