# `cron-learning-all` redundancy review — 2026-09-12

Research-only. This document does not change Railway variables, Cron, services, Production decisions, LINE, purchases, or Production data.

## Current natural behavior

Both services currently run every 15 minutes during `23,0-14` UTC (about 08:00–23:45 JST):

- `cron-final-check` → `run_final_pg.py` → `v25_final_realtime_pipeline_pg.py` → `v21_realtime_collector_pg_safe.py`
- `cron-learning-all` → `run_learning_all_realtime_pg.py` → `v21_realtime_collector_pg_safe.py`

The safe v21 collector supports `COLLECT_SCOPE=all + TARGET_ID_SCOPE=candidates`: the full deadline-window `target` remains the collection set while only downstream decision IDs are narrowed. This behavior is contract-tested in CI.

The learning wrapper separately forces `COLLECT_SCOPE=all`, the same 30-minute-before-deadline window, and label `learning_all`. Natural evidence on 2026-09-12 JST repeatedly showed the same race sets and almost identical saved-row counts. No Cron or service setting was changed during this research.

## Live identity inventory: duplication is nearly complete

Production DB observations run read-only with `PGOPTIONS=-c default_transaction_read_only=on` and static rejection of mutation primitives.

Verified realtime-odds inventory around the current audit window:

- `v2_realtime_odds_snapshots`: about `507 MB`
- `final_ab`: about `986k` rows
- `learning_all`: about `397k` rows
- final-vs-learning identity overlap: about `397k` rows
- recent identity overlap: **99.9843%**

Across odds + weather + exhibition + entry + race-condition + racer-condition, current `learning_all` contains about `461k` rows and roughly `103 MB` of logical tuple payload. Recent seven-day learning growth averages about **10,890.71 rows/day** and **2.32 MiB/day** of logical tuple payload. These are logical-storage/write observations, not claims of proportional physical Railway-volume reclaim.

Identity duplication is near-total, but identity duplication is not equivalent to feature/output redundancy.

## Movement features differ materially

An earlier fixed inventory of `396,410` overlapping odds identities found:

- equal current odds: `384,472` (**96.99%**)
- equal market rank: `387,059` (**97.64%**)
- equal `prev_odds`: `314,260` (**79.28%**)
- all compared movement features equal: `313,458` (**79.07%**)
- movement-feature differences: `82,952` (**20.93%**)

The compared movement set includes previous odds/rank, delta / percentage delta, rank delta, favorite/low-odds flags, and drift/steam flags.

## Critical indirect Production dependency: previous odds are cross-label

Current `v21_realtime_collector_pg.py::_fetch_previous_odds(rid)` selects the latest realtime odds rows for a race without filtering `snapshot_label`. The safe collector reuses this helper when building new odds rows.

Therefore a new `final_ab` row can use a `learning_all` row as its immediate previous market sample. Derived fields include `prev_odds`, odds delta/percentage delta, previous market rank, market-rank delta, and the drift/steam flags.

This reaches Production scoring. `v22_realtime_decision_engine_pg.py` applies:

- `is_odds_steam` → realtime score `+0.3`
- `is_odds_drift` → realtime score `-0.5`

Thus “no Production code hard-codes literal `learning_all`” remains true, but does **not** imply independence.

## Read-only coupling audit: direct evidence

The latest coupling audit run at about 13:18 JST observed:

- overlapping final/learning odds identities: `397,250`
- learning timestamp before final: `188,079`
- final timestamp before learning: `209,171`
- final `prev_odds` exactly equals current learning odds: **`187,840` rows**
- previous odds + previous rank both exactly match current learning: **`187,840` rows**
- direct predecessor matches within 180 seconds: **`176,946`**
- direct predecessor matches in the latest seven completed days: **`31,617`**
- average direct learning→final gap: about **77.54 seconds**

Counts can move slightly while the natural collectors keep running. The safety conclusion does not depend on the exact minute-by-minute total: a very large cross-label predecessor relationship is empirically confirmed.

## Counterfactual proxy: stopping the learning hop can change v22 movement score

Because realtime tables retain one current row per `(race_id,snapshot_label,ticket)`, exact historical replay of every overwritten same-label snapshot is unavailable. A bounded one-step proxy is therefore used only where a final row demonstrably used current learning odds as `prev_odds` and that learning row itself has a prior odds value.

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

This does not mean 15,419 historical recommendations would flip. It proves that removing the learning hop can materially change a Production-scored feature.

## Saved-decision intersection: sample is too small to prove safety

The same read-only audit joined the coupling evidence to the currently retained `v2_realtime_decisions` rows for `decision_label='final_ab'`.

Current retained sample:

- final decision rows: **4** across 4 races
- rows on a directly learning-coupled odds path: **1**
- that row's stored recommendation: **WATCH**
- stored drift/steam flag on that row: neither
- one-step proxy recommendation change: **0**
- BUY→other proxy changes: `0`
- other→BUY proxy changes: `0`

This is useful only as an intersection check. Four retained decision rows are far too few to establish output invariance. The much larger feature-level coupling evidence therefore remains the controlling safety signal.

## Consequence: full learning pause is blocked

A future `LEARNING_ALL_ENABLED=0` observation is not a harmless reversible collection test. Stopping the learning collector changes the time interval/source available to `final_ab.prev_odds`, which can change steam/drift flags and v22 realtime scores.

Accordingly:

- **do not pause or disable `cron-learning-all` under current feature semantics** without explicit Production/model-impact approval and a stronger output-invariance experiment;
- historical `learning_all` rows remain preservation-by-default;
- making `_fetch_previous_odds` label-scoped would itself change Production feature semantics and also requires model-impact review;
- the 4-row retained decision sample must not be used to infer safety of a full pause.

## Capacity direction after the dependency finding

### Keep both collectors

Preserves current Production feature semantics exactly, but continues nearly duplicated collection/write growth.

### Full learning pause

**Blocked as an output-neutral capacity experiment.** It can alter `final_ab` movement features and v22 scores.

### Odds-only learning path

This is the safest design candidate if current cross-label market-movement cadence must be preserved while duplicated non-odds collection is reduced.

Current logical tuple split:

- odds learning bytes: `75,876,808` / `103,050,968` = about **73.63%**
- non-odds learning bytes: `27,174,160` = about **26.37%**
- recent seven-day non-odds logical payload: `4,575,256` bytes
- recent non-odds average: about **653,608 bytes/day** (~0.62 MiB/day)
- recent non-odds rows: `10,912`, about **1,558.9 rows/day**

Odds-only learning would preserve most current learning storage because odds dominate the payload. It is **not a major capacity-reclaim lever**, but it could eliminate duplicated beforeinfo HTTP work and about 26% of learning tuple payload while preserving the cross-label odds predecessor mechanism.

Any implementation remains research-only/default-off until separately approved; no Production collector has been changed.

## Consumer/isolation CI contract

Research CI protects these assumptions:

- final/nightly scheduled chains default to `final_ab`;
- no other top-level runtime Python script silently hard-codes `learning_all`;
- the learning wrapper remains collection-only with no decision/notifier/purchase wiring;
- candidate targeting cannot narrow the full snapshot collection set;
- read-only coupling/decision measurement cannot mutate Production data.

The key architectural lesson is that literal-label dependency and semantic dependency are different. Future cleanup work must check both.

## Safe next research sequence

1. Specify an odds-only learning design in an isolated research module with no runtime wiring and default-off semantics.
2. Test that the design preserves odds collection timing/label semantics while skipping only non-odds acquisition paths.
3. Quantify expected HTTP/write savings; do not claim proportional physical volume shrink.
4. Separately research a replayable movement-history architecture so future capacity changes do not depend on implicit cross-label ordering.
5. Treat any full pause, Cron disable, or label-scoped previous-odds rewrite as a Production/model-impact change requiring explicit approval.

## Current decision

`IDENTITY_DUPLICATION_CONFIRMED / RECENT_IDENTITY_OVERLAP_99_9843PCT / LEARNING_GROWTH_10891_ROWS_PER_DAY / MOVEMENT_FEATURE_DIFFERENCE_20_93PCT / INDIRECT_CROSS_LABEL_PREVIOUS_ODDS_DEPENDENCY_EMPIRICALLY_CONFIRMED / DIRECT_PREDECESSOR_MATCHES_ABOUT_188K / RECENT7_DIRECT_PREDECESSOR_MATCHES_31617 / COUNTERFACTUAL_PROXY_SCORE_CHANGED_15419 / RECENT7_PROXY_SCORE_CHANGED_10805 / RETAINED_FINAL_DECISIONS_ONLY_4 / ONE_RETAINED_WATCH_DIRECTLY_COUPLED / DECISION_SAMPLE_TOO_SMALL_FOR_INVARIANCE / V22_STEAM_DRIFT_SCORE_SENSITIVE / FULL_LEARNING_PAUSE_BLOCKED / HISTORICAL_LEARNING_ROWS_PRESERVE / ODDS_ONLY_REDESIGN_RESEARCH_CANDIDATE / NO_SERVICE_DISABLE_AUTHORIZED / NO_CRON_CHANGE / NO_DB_DELETE / NO_PRODUCTION_CHANGE`
