# `cron-learning-all` redundancy review — 2026-09-12

Research-only. This document does not change Railway variables, Cron, services, Production decisions, LINE, purchases, or Production data.

## Current natural behavior

Both services currently run every 15 minutes during `23,0-14` UTC (about 08:00–23:45 JST):

- `cron-final-check` → `run_final_pg.py` → `v25_final_realtime_pipeline_pg.py` → `v21_realtime_collector_pg_safe.py`
- `cron-learning-all` → `run_learning_all_realtime_pg.py` → `v21_realtime_collector_pg_safe.py`

The safe v21 collector supports `COLLECT_SCOPE=all + TARGET_ID_SCOPE=candidates`: the full deadline-window `target` remains the collection set while only downstream decision IDs are narrowed. This behavior is contract-tested in CI.

The learning wrapper separately forces `COLLECT_SCOPE=all`, the same 30-minute-before-deadline window, and label `learning_all`.

Natural evidence on 2026-09-12 JST repeatedly showed the same race sets and almost identical saved-row counts. No Cron or service setting was changed during this research.

## Live identity inventory: duplication is nearly complete

All Production DB observations below run read-only with `PGOPTIONS=-c default_transaction_read_only=on` and static rejection of mutation primitives.

Latest verified realtime-odds inventory:

- `v2_realtime_odds_snapshots`: `506,904,576` bytes / `1,383,910` exact rows
- `final_ab`: `986,420` rows / `8,453` races
- `learning_all`: `397,370` rows / `3,376` races
- final-vs-learning `(race_id,ticket)` overlap: `396,410`
- learning-only odds identities: `960`
- equal current odds in overlap: `384,472` (**96.99%**)
- average absolute collection-time gap: about `72.60s`

Across odds + weather + exhibition + entry + race-condition + racer-condition, current `learning_all` contains `460,920` rows and about `103,050,968` bytes of logical tuple payload (~98.3 MiB; not physical reclaim). Only `1,152` stored identities lack the same identity under `final_ab`.

For the seven completed days immediately before the current date:

- `learning_all`: `76,235` rows
- `final_ab`: `139,386` rows
- recent learning-only identities: **12**
- recent identity overlap: **99.9843%**
- all 12 recent learning-only identities are exhibition rows
- average learning growth: about **10,890.71 rows/day**
- average logical tuple payload: about **2,429,374 bytes/day** (~2.32 MiB/day)

Identity duplication is therefore near-total, but identity duplication is not equivalent to feature/output redundancy.

## Movement features differ materially

For `396,410` overlapping odds identities:

- equal current odds: `384,472` (**96.99%**)
- equal market rank: `387,059` (**97.64%**)
- equal `prev_odds`: `314,260` (**79.28%**)
- all compared movement features equal: `313,458` (**79.07%**)
- movement-feature differences: `82,952` (**20.93%**)

The compared movement set includes previous odds/rank, delta / percentage delta, rank delta, favorite/low-odds flags, and drift/steam flags.

## Critical indirect Production dependency: previous odds are cross-label

Current `v21_realtime_collector_pg.py::_fetch_previous_odds(rid)` selects the latest realtime odds rows for a race without filtering `snapshot_label`. The safe collector reuses this helper when building new odds rows.

Therefore a new `final_ab` row can use a `learning_all` row as its immediate previous market sample. The derived fields include:

- `prev_odds`
- `odds_delta`
- `odds_delta_pct`
- `prev_market_rank`
- `market_rank_delta`
- `is_odds_drift`
- `is_odds_steam`

This reaches Production scoring. `v22_realtime_decision_engine_pg.py` applies:

- `is_odds_steam` → realtime score `+0.3`
- `is_odds_drift` → realtime score `-0.5`

Thus “no Production code hard-codes literal `learning_all`” remains true, but does **not** imply independence.

## Read-only coupling audit: direct evidence

A dedicated read-only audit now quantifies the cross-label predecessor relationship.

Across the `396,410` overlapping `(race_id,ticket)` odds identities:

- learning timestamp before final timestamp: `188,319`
- final timestamp before learning timestamp: `208,091`
- final `prev_odds` exactly equals current learning odds: **`188,080` rows**
- final `prev_odds` and `prev_market_rank` both exactly match current learning values: **`188,080` rows**
- direct predecessor evidence within 180 seconds: **`177,186` rows**
- direct predecessor evidence in the latest seven completed days: **`31,617` rows**
- average direct learning→final gap: about **77.49 seconds**

This is strong empirical evidence that the learning collector is currently part of the effective input cadence for later final movement features.

## Counterfactual proxy: stopping the learning hop can change v22 movement score

Because realtime tables retain one current row per `(race_id,snapshot_label,ticket)`, exact historical replay of every overwritten same-label snapshot is unavailable. The audit therefore uses a bounded one-step proxy where:

1. a final row demonstrably used current learning odds as `prev_odds`; and
2. that learning row itself has a non-null `prev_odds`.

For `169,758` such rows:

- stored drift rows: `1,122`
- proxy drift rows without the immediate learning hop: `12,584`
- stored steam rows: `282`
- proxy steam rows: `3,900`
- rows whose drift/steam movement score changes: **`15,419`**
- latest seven completed days with changed proxy movement score: **`10,805`**
- proxy score higher than stored: `3,791`
- proxy score lower than stored: `11,628`
- possible movement-score delta in the proxy: **`-0.8` to `+0.8`**

This proxy is not a claim that 15,419 saved BUY/WATCH/SKIP decisions would flip. It proves something narrower and sufficient for the safety gate: removing the learning hop can materially change a Production-scored feature, so a learning pause is not output-neutral by construction.

## Consequence: full learning pause is blocked

A future `LEARNING_ALL_ENABLED=0` observation is no longer classified as a harmless reversible collection test. Stopping the learning collector changes the time interval/source available to `final_ab.prev_odds`, which can change steam/drift flags and v22 realtime scores.

Accordingly:

- **do not pause or disable `cron-learning-all` under current feature semantics** without explicit Production/model-impact approval and a stronger output-invariance experiment;
- historical `learning_all` rows remain preservation-by-default;
- making `_fetch_previous_odds` label-scoped would itself change Production feature semantics and also requires model-impact review;
- deletion of historical learning rows is not a prerequisite for capacity research and remains out of scope.

## Capacity direction after the dependency finding

### Keep both collectors

Preserves current Production feature semantics exactly, but continues nearly duplicated collection/write growth.

### Full learning pause

**Blocked as an output-neutral capacity experiment.** It can alter `final_ab` movement features and v22 scores.

### Odds-only learning path

This is the safest design candidate if the goal is to preserve current cross-label market-movement cadence while removing redundant non-odds collection.

Current logical tuple split:

- odds learning bytes: `75,876,808` / `103,050,968` = about **73.63%**
- non-odds learning bytes: `27,174,160` = about **26.37%**
- recent seven-day non-odds logical payload: `4,575,256` bytes
- recent non-odds average: about **653,608 bytes/day** (~0.62 MiB/day)
- recent non-odds rows: `10,912`, about **1,558.9 rows/day**

So odds-only learning would preserve most current learning storage because odds dominate the payload. It is **not a major capacity-reclaim lever**, but it could eliminate duplicated beforeinfo HTTP work and about 26% of learning tuple payload while preserving the cross-label odds predecessor mechanism.

Any implementation remains default-off research until separately approved; no Production collector has been changed.

## Consumer/isolation CI contract

Research CI protects these assumptions:

- final/nightly scheduled chains default to `final_ab`;
- no other top-level runtime Python script silently hard-codes `learning_all`;
- the learning wrapper remains collection-only with no decision/notifier/purchase wiring;
- candidate targeting cannot narrow the full snapshot collection set;
- read-only coupling measurement cannot mutate Production data.

The key architectural lesson is that literal-label dependency and semantic dependency are different. Future cleanup work must check both.

## Safe next research sequence

1. Quantify which saved final decision candidates intersect learning-derived movement flags, read-only.
2. Specify an odds-only learning design as a separate default-off research implementation, without deployment.
3. Quantify HTTP/write savings and preserve current odds predecessor timing in tests.
4. Do not claim proportional physical Railway-volume shrink from logical-row savings.
5. Treat any full pause, Cron disable, or label-scoped previous-odds rewrite as a Production/model-impact change requiring explicit approval.

## Current decision

`IDENTITY_DUPLICATION_CONFIRMED / RECENT_IDENTITY_OVERLAP_99_9843PCT / LEARNING_GROWTH_10891_ROWS_PER_DAY / MOVEMENT_FEATURE_DIFFERENCE_20_93PCT / INDIRECT_CROSS_LABEL_PREVIOUS_ODDS_DEPENDENCY_EMPIRICALLY_CONFIRMED / DIRECT_PREDECESSOR_MATCHES_188080 / RECENT7_DIRECT_PREDECESSOR_MATCHES_31617 / COUNTERFACTUAL_PROXY_SCORE_CHANGED_15419 / RECENT7_PROXY_SCORE_CHANGED_10805 / V22_STEAM_DRIFT_SCORE_SENSITIVE / FULL_LEARNING_PAUSE_BLOCKED / HISTORICAL_LEARNING_ROWS_PRESERVE / ODDS_ONLY_REDESIGN_RESEARCH_CANDIDATE / NO_SERVICE_DISABLE_AUTHORIZED / NO_CRON_CHANGE / NO_DB_DELETE / NO_PRODUCTION_CHANGE`
