# `cron-learning-all` redundancy review — 2026-09-12

Research-only. This document does not change Railway variables, Cron, services, Production decisions, LINE, purchases, or Production data.

## Current natural behavior

Both services currently run every 15 minutes during `23,0-14` UTC (about 08:00–23:45 JST):

- `cron-final-check` → `run_final_pg.py` → `v25_final_realtime_pipeline_pg.py` → `v21_realtime_collector_pg_safe.py`
- `cron-learning-all` → `run_learning_all_realtime_pg.py` → `v21_realtime_collector_pg_safe.py`

The safe v21 collector supports `COLLECT_SCOPE=all + TARGET_ID_SCOPE=candidates`: `target` remains the full deadline-window collection set, while `target_id_rows` is only the downstream decision subset. `collection_ids` and the data-collection loop both use the full `target`. This behavior is now frozen by CI so candidate targeting cannot silently narrow snapshot collection.

The learning wrapper separately forces `COLLECT_SCOPE=all`, the same 30-minute-before-deadline window, and a separate `learning_all` label.

Natural evidence on 2026-09-12 JST:

- 11:00: both collectors targeted the same 9 races and each saved 1080 trifecta odds rows.
- 11:15: both targeted the same 11 races, saved 1200 odds rows, and observed the same one official-odds miss.
- 12:00: both targeted the same 9 races and saved 1080 odds rows.
- 12:15: both targeted the same 10 races, saved 1080 odds rows, 30 exhibition rows, and 60 entry rows; both observed the same one odds miss.
- 12:30: start-time drift moved one edge race in/out of the 30-minute window, but 9/10 race identities still overlapped; both saved 1080 odds rows and 60 entry rows.

This confirms duplicate acquisition/update work under normal Production timing. No Cron or service setting was changed during this research.

## Live label inventory: identity duplication is nearly complete

All queries below ran through the research-only live audit with `PGOPTIONS=-c default_transaction_read_only=on`, static rejection of DB mutation primitives, and SELECT/catalog queries only.

Latest `v2_realtime_odds_snapshots` inventory:

- relation size: `506,904,576` bytes
- exact rows: `1,383,910`
- `final_ab`: `986,420` rows / `8,453` races
- `learning_all`: `397,370` rows / `3,376` races
- `final_ab_debug`: `120` rows

On `(race_id,ticket)` identity:

- `learning_all`: `397,370` rows
- overlap with `final_ab`: `396,410`
- learning-only: `960` rows / 8 races
- equal current odds within overlap: `384,472` (**96.99%**)
- different current odds: `11,938`
- average absolute collection-time difference: about `72.60s`

The other realtime tables show the same coverage pattern:

| Table | `learning_all` | overlap with `final_ab` | learning-only | payload-identical in overlap |
|---|---:|---:|---:|---:|
| weather | 3,383 | 3,377 | 6 | 3,269 |
| exhibition | 16,188 | 16,080 | 108 | **16,080** |
| entry | 20,298 | 20,262 | 36 | 20,010 |
| race condition | 3,383 | 3,377 | 6 | 3,269 |
| racer condition | 20,298 | 20,262 | 36 | 19,986 |

Across odds plus these five tables, `learning_all` contains `460,920` identities and only `1,152` do not have the same identity under `final_ab`.

## Recent seven-day coverage and growth

A separate read-only growth audit uses the seven completed race dates before the current date, so the in-progress current day does not distort the rate.

Across the six realtime tables:

- `learning_all` rows in the seven completed days: `76,235`
- same-period `final_ab` rows: `139,386`
- recent learning-only identities: **12**
- recent identity overlap: **99.9843%**
- the 12 recent learning-only identities are exhibition rows; odds/weather/entry/race-condition/racer-condition had `0` recent learning-only identities
- average `learning_all` rows added per completed day: about **10,890.71**
- average logical tuple payload per completed day: about **2,429,374 bytes/day** (~2.32 MiB/day)

Current stored `learning_all` logical tuple payload across the six tables is about `103,050,968` bytes (~98.3 MiB). This is a logical-row measurement only: it excludes index/heap overhead and does **not** imply an equal physical Railway-volume reduction from deletion.

## Important counterpoint: odds movement features are not fully redundant

The two services are offset in time, so the second label acts as a separate temporal sample even when it covers the same race/ticket.

For the `396,410` overlapping odds identities:

- equal current odds: `384,472` (**96.99%**)
- equal market rank: `387,059` (**97.64%**)
- equal `prev_odds`: `314,260` (**79.28%**)
- all compared movement features equal: `313,458` (**79.07%**)
- movement-feature difference: `82,952` (**20.93%**)

The compared movement set includes market rank, previous odds, odds delta / percentage delta, previous market rank, rank delta, favorite/low-odds flags, and drift/steam flags.

Therefore the correct conclusion is nuanced:

- **coverage/storage identity is almost entirely duplicated**;
- **Production decision coverage does not depend on the learning label** based on the current scheduled chain;
- but `learning_all` is **not byte-for-byte or feature-for-feature redundant**: it preserves an independent, roughly one-minute-shifted odds-change trajectory for research.

This is why this Draft does not classify the label as disposable historical data.

## Consumer search and Production-path boundary

A bounded repository search for the literal `learning_all` found the learning producer wrapper, documentation/tests, Railway bridge allowlisting, and repository classification text. No hard-coded Production model/decision/LINE consumer of the literal label was found.

The scheduled Production chain instead defaults to `final_ab`:

- `run_final_pg.py` sets `SNAPSHOT_LABEL=final_ab` and `DECISION_LABEL=final_ab` if absent;
- `v25_final_realtime_pipeline_pg.py` passes the same final label through collection, targeted v22 decision, exhibition Shadow, and notifier stages;
- `v22_realtime_decision_engine_pg.py`, `v22_exhibition_shadow_pg.py`, and `v23_line_notifier_batch_pg.py` default to `final_ab`;
- `run_v22_targeted_pg.py` passes the requested label through and contains no `learning_all` literal;
- `run_nightly_results_pg.py` defaults to `final_ab`, and the latest natural nightly logs also printed `SNAPSHOT_LABEL=final_ab`.

The learning wrapper itself only launches the safe collector, uses a separate target-race-id file, and explicitly has no LINE, Production judgment, or purchase processing.

## CI contract added by this Draft

`tests/test_learning_all_redundancy_contract.py` now fails if:

- the scheduled final/nightly chain stops defaulting to `final_ab`;
- a known Production runtime starts hard-coding `learning_all`;
- any other top-level runtime Python script begins hard-coding `learning_all`;
- the learning wrapper gains decision/notifier/purchase wiring;
- `TARGET_ID_SCOPE=candidates` starts narrowing the full snapshot collection set instead of only decision IDs.

This protects the current isolation assumption against future drift. It does not forbid research/CI code under subdirectories from analyzing the historical label.

## Capacity options for future approval

No option below is authorized by this document.

The evidence supports three distinct future choices:

1. **Keep both collectors unchanged.** This preserves the extra shifted movement trajectory but continues near-total identity duplication and roughly 10.9k additional logical rows per completed day.
2. **Reversible full learning pause.** If separately approved, `LEARNING_ALL_ENABLED=0` can be observed for a bounded natural race day while final-check remains untouched. Existing historical learning rows would be preserved. This reduces future duplicate collection but deliberately gives up the second temporal sample during the observation period.
3. **Research an odds-only learning path.** About 73.6% of current learning logical tuple bytes are odds rows, and those are the rows where meaningful movement-feature divergence was demonstrated. The non-odds learning tables account for about 26.4% of current learning tuple payload and are much more payload-redundant. A future odds-only design could preserve the distinct market-movement series while avoiding duplicated weather/exhibition/entry/condition writes. This requires code and Production-behavior changes and therefore remains research-only until separately approved.

## Safest future validation sequence

Before any Production pause/change:

1. keep the static isolation contract green;
2. recheck natural final-vs-learning overlap and current service configuration;
3. decide explicitly whether the research value of the second movement trajectory should be preserved;
4. if a reversible pause is approved, leave all historical `learning_all` rows intact and change only the bounded collector behavior;
5. observe at least one full eligible natural race day without manual rerun/backfill;
6. require normal final-check race coverage, odds completeness, final decision/LINE behavior, nightly evaluations, and scheduled-job health;
7. roll back immediately if a missing-data regression is attributable to the pause;
8. treat permanent retirement, odds-only redesign, or historical-row deletion as separate later approvals.

## Current decision

`IDENTITY_DUPLICATION_CONFIRMED / RECENT_IDENTITY_OVERLAP_99_9843PCT / LEARNING_GROWTH_10891_ROWS_PER_DAY / LEARNING_LOGICAL_TUPLES_2_43MB_PER_DAY / MOVEMENT_FEATURE_DIFFERENCE_20_93PCT / PRODUCTION_LITERAL_CONSUMER_NOT_FOUND / FINAL_FULL_WINDOW_COLLECTION_CONTRACT_PASS / TOP_LEVEL_RUNTIME_CONSUMER_GUARD_PASS / HISTORICAL_LEARNING_ROWS_PRESERVE / ODDS_ONLY_REDESIGN_RESEARCH_CANDIDATE / REVERSIBLE_OBSERVATION_REQUIRES_APPROVAL / NO_SERVICE_DISABLE_AUTHORIZED / NO_CRON_CHANGE / NO_DB_DELETE / NO_PRODUCTION_CHANGE`
