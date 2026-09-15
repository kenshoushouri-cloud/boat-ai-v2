# V4 odds archive consumer audit

Status: `RESEARCH_ONLY / READ_ONLY_FINDINGS / NO_RETENTION_CUTOFF / NO_PRODUCTION_MUTATION`

Date: 2026-09-15 JST

## Purpose

Determine whether the full historical `v2_odds_trifecta` relation must remain resident in the live Railway PostgreSQL database, or whether historical rows can eventually move to an external recoverable archive without affecting normal current-day operation.

This document does not authorize data export, deletion, retention changes, schema changes, service/Cron changes, or a Railway plan migration.

## Confirmed live-path scope

### Daily preparation

`run_daily_data_prepare_pg.py` is target-date scoped:

- `REPAIR_START_DATE=TARGET_DATE`
- `REPAIR_END_DATE=TARGET_DATE`
- odds audit joins `v2_odds_trifecta` only for `r.race_date = TARGET_DATE`

The normal daily preparation path therefore does not require all historical odds to answer the current-day quality check.

### Realtime FINAL collection

`v21_realtime_collector_pg_safe.py` calls the legacy `fetch_day_base(TARGET_DATE)` loader.

The underlying base-odds query is bounded by the target day's race-id prefix:

`race_id >= day_prefix AND race_id < next_day_prefix`

The safe collector also attempts direct official `odds3t` first. Base-table odds are accepted only as a complete 120/60/24 fallback. Partial/stale base odds are rejected fail-closed.

### Legacy/current PRE helper

`v24_pre_candidate_notifier_pg.py::_fetch_live_day_rows(date_str)` also bounds `v2_odds_trifecta` to the requested day using the same day-prefix / next-day-prefix pattern.

Therefore the key current-day PRE/FINAL data-loading paths do not inherently require the full historical odds relation to stay online.

### Current-day odds window collector

`run_odds_window_pg.py` is an active current-day acquisition/completeness path, not an archive consumer. It selects races for `TARGET_DATE`, checks the selected race IDs in `v2_odds_trifecta`, and may fetch/upsert missing pre-deadline odds. It belongs on the online/live side of the ownership split and should not be replaced by historical archive read-through.

## Historical consumers still blocking archive-only storage

Default-branch code still contains historical consumers that assume older odds are directly queryable from PostgreSQL. Examples include:

- historical/backtest feature analysis;
- historical month gap/repair checks;
- backtest readiness/diagnostic utilities;
- feature laboratory / model-comparison utilities;
- N01/N02 walk-forward / diagnostics / rolling analyses;
- probability-calibration analyses;
- V24 historical Motor2 / low-mid grid / transition diagnostics;
- historical odds-window research.

These tools are valuable and should not simply lose data access. They must either:

1. be migrated to an external archive/read-through interface; or
2. be explicitly retired as obsolete after dependency review.

Until then, deleting old online odds rows would break legitimate research/reproducibility workflows.

## Archive-consumer coverage already proven

The branch now has real-data Production-read-only evidence for several independent consumer classes.

### Historical readiness

`research_backtest_ready_archive.py` reproduces `pg_backtest_ready_check.py`'s odds-completeness role with a verified archive partition while entries/results remain in read-only PostgreSQL. July archive-vs-online per-race odds coverage has passed.

### Realtime `final_ab` feature analysis

`analyze_final_ab_features_pg.py` has a research archive path for its historical realtime odds input. July `final_ab` real-data export/readback and consumer online-vs-archive equivalence passed.

### Feature Lab base odds

Run `34931688532` / job `104261037806` passed using July `v2_odds_trifecta` as the archived odds source while all other inputs remained read-only PostgreSQL:

- online odds rows: 588,156
- archive odds rows: 588,156
- eligible races: 4,893
- all summary outputs matched exactly for `BASELINE`, `PREVIOUS_ST_FIXED`, `RACER_COURSE`, and `PREVIOUS_ST_PLUS_RACER_COURSE`
- `FEATURE_LAB_ARCHIVE_RESULT=PASS_READ_ONLY`

The original Production/research table was not modified; Feature Lab result saving was disabled for the equivalence run.

### Motor/boat historical A/B

A strict research harness now intercepts only `compare_motor_boat_ab_pg.py`'s historical `v2_odds_trifecta` fetch and substitutes the verified July archive. It runs the original analysis once online and once archive-backed and requires exact stdout equality. This is research-only and does not change the default script. Evidence status is recorded in PR #363 CI/comments once the real-data job completes.

## Current migration matrix

| consumer / path | role | current online dependency | migration state |
|---|---|---|---|
| daily data prepare | live current-day | target date only | KEEP ONLINE |
| v21 safe realtime collector / base fallback | live current-day | same target-day races | KEEP ONLINE |
| v24 PRE helper | legacy/current-day | same target-day races | retire with old PRE; no history requirement |
| `run_odds_window_pg.py` | active acquisition | selected current-day races | KEEP ONLINE |
| historical readiness | research/diagnostic | old base odds | ARCHIVE EQUIVALENCE PROVEN |
| Feature Lab | research | old base odds | ARCHIVE EQUIVALENCE PROVEN |
| `analyze_final_ab_features_pg.py` | research | old realtime `final_ab` | ARCHIVE EQUIVALENCE PROVEN |
| `compare_motor_boat_ab_pg.py` | historical research | old base odds | ARCHIVE EQUIVALENCE TEST ADDED |
| N01/N02 historical family | historical research | old base odds | MIGRATION PENDING |
| probability calibration | historical research | old base odds | MIGRATION PENDING |
| V24 historical Motor2 family | historical research | old base odds | MIGRATION PENDING |
| old month-gap/repair utilities | repair/diagnostic | old base odds | REVIEW: archive-aware vs obsolete |

The remaining direct-SQL count is therefore a research-migration backlog, not proof that those old odds must remain on the live Production working set permanently.

## Railway service findings

Two monthly Production services have names that no longer match their actual commands:

### `historical-backfill`

Current start command:

`python -u diagnose_motor2_parser_pg.py`

The script is a Motor2 parser diagnostic over `v2_race_entries` plus official-page fetches. It does not function as a broad historical odds backfill and contains no persistent DB-write path.

### `backtest-analysis`

Current start command:

`python -u collect_v24_motor2_forward_shadow_pg.py`

The current fixed old test invocation writes Motor2 Shadow with a stable `(race_id,ticket,run_class,window_name,snapshot_key)` conflict key. Re-running the same fixed test key updates the same logical rows rather than creating an unbounded monthly history. These `manual/test` rows are not Production scoring input, although broad historical diagnostic reports can include them.

Both services are candidates for a separate zero-consumer/service-retirement review. They must not be changed or deleted without explicit Production approval.

## Target archive architecture

The intended split is:

### Online Railway PostgreSQL

Keep all data required for normal live operation, current Forward scoring and reproducibility, including the operational date slice required by current collectors.

### External historical archive

Keep older raw odds needed for backtesting, retraining, audit and future research in a deterministic recoverable format with:

- bounded date/month partitions;
- exact row counts;
- min/max race date and race id;
- schema/contract version;
- uncompressed and compressed sizes;
- SHA-256 manifest;
- restore/readback test evidence.

Historical consumers should access this archive through a defined read-through/research path rather than forcing every old row to remain in the live operational database.

## Retention scenario result

Production read-only run `34931343677` measured 7/14/30/60-day reference windows. For `v2_odds_trifecta` plus realtime `final_ab` / `learning_all`, a 30-day reference leaves about 232.1 MB of logical tuple payload online and about 883.9 MB (~79.2%) in the cold/archive-reviewable side.

This is a capacity/reference result only. `30d` is **not** an approved retention rule, and logical payload bytes are not a promise of physical Railway Volume reclaim.

## Retention-boundary rule

No arbitrary rolling-day cutoff is preregistered here.

A future online retention boundary may be chosen only after:

1. all active live consumers are mapped;
2. historical consumers have archive access or are retired;
3. normal operation proves it never needs archived dates unexpectedly;
4. daily growth is measured;
5. archive restore/readback is proven;
6. exact migration size/headroom is calculated;
7. the user explicitly approves the Production migration/removal action.

## Current decision

`FULL_HISTORY_NOT_REQUIRED_BY_LIVE_LOADERS / ARCHIVE_EQUIVALENCE_EXPANDING / 30D_REFERENCE_ONLY / HISTORICAL_MIGRATION_BACKLOG_REMAINS / NO_DELETE / NO_RETENTION_CUTOFF / NO_SERVICE_CHANGE`
