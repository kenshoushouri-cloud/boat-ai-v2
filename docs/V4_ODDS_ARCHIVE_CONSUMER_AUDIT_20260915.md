# V4 odds archive consumer audit

Status: `RESEARCH_ONLY / READ_ONLY_FINDINGS / NO_RETENTION_CUTOFF / NO_PRODUCTION_MUTATION`

Date: 2026-09-15 JST

## Purpose

Determine whether the full historical `v2_odds_trifecta` relation must remain resident in the live Railway PostgreSQL database, or whether historical rows can eventually move to an external recoverable archive without affecting normal current-day operation.

This document does not authorize data export to a permanent store, deletion, retention changes, schema changes, service/Cron changes, or a Railway plan migration.

## Confirmed live-path scope

### Daily preparation

`run_daily_data_prepare_pg.py` is target-date scoped:

- `REPAIR_START_DATE=TARGET_DATE`
- `REPAIR_END_DATE=TARGET_DATE`
- odds audit joins `v2_odds_trifecta` only for `r.race_date = TARGET_DATE`

The normal daily preparation path therefore does not require all historical odds to answer the current-day quality check.

### Realtime FINAL collection

`v21_realtime_collector_pg_safe.py` calls the target-day base loader. The base-odds query is bounded by the target day's race-id prefix:

`race_id >= day_prefix AND race_id < next_day_prefix`

The safe collector attempts direct official `odds3t` first. Base-table odds are accepted only as a complete fallback; partial/stale base odds fail closed.

### Legacy/current PRE helper

`v24_pre_candidate_notifier_pg.py::_fetch_live_day_rows(date_str)` also bounds `v2_odds_trifecta` to the requested day. Old full history is not inherently required by this current-day load path.

### Current-day odds window collector

`run_odds_window_pg.py` is an active current-day acquisition/completeness path. It checks selected current-day race IDs and may fetch/upsert missing pre-deadline odds. This remains on the online/live side and is not an archive consumer.

## Verified archive contract

The research branch uses a deterministic monthly-partition contract:

- bounded calendar-month/date range;
- exact schema in manifest;
- exact row count;
- canonical payload SHA-256;
- compressed file SHA-256;
- deterministic gzip payload;
- readback verification;
- `source_rows_deleted=false` for pilots;
- PostgreSQL read-only for all equivalence runs;
- no permanent upload yet.

The current V1 read-through deliberately requires one partition to cover the requested range exactly. It does **not** silently stitch partial online/archive evidence or multiple archive months. Cross-month stitching will be added only after a permanent archive destination is chosen, with explicit gap/overlap detection and fail-closed behavior.

## Real-data archive equivalence already proven

### July base odds archive

A July 2026 `v2_odds_trifecta` pilot exported and read back **588,156 rows** with exact manifest/hash verification. Pilot files were ephemeral and deleted after CI. The compressed archive file was 8,138,479 bytes.

### Historical readiness

`research_backtest_ready_archive.py` reproduces the odds-completeness role of the historical readiness check while entries/results stay in read-only PostgreSQL. July archive-vs-online coverage passed.

### Realtime `final_ab` analysis

`analyze_final_ab_features_pg.py` has a research-only archive path for old `final_ab` evidence. July export/readback and online-vs-archive analysis equivalence passed.

### Feature Lab

Run `34931688532` / job `104261037806` passed:

- online odds rows: 588,156
- archive odds rows: 588,156
- eligible races: 4,893
- exact summary equality for `BASELINE`, `PREVIOUS_ST_FIXED`, `RACER_COURSE`, and `PREVIOUS_ST_PLUS_RACER_COURSE`
- `FEATURE_LAB_ARCHIVE_RESULT=PASS_READ_ONLY`

### Motor/boat historical A/B

The original `compare_motor_boat_ab_pg.py` is run unchanged once against online odds and once with only its `v2_odds_trifecta` reads intercepted by the verified archive. Exact stdout equality passed.

### Historical consumer matrix run

Run `34970777172` / job `104386249410` completed successfully with exact online-vs-archive stdout equality for all six unchanged historical consumers:

- `backtest_prob_calibration_pg.py`
  - ready races: 4,889
  - ticket rows: 586,680
  - stdout SHA-256: `6df845c844321f6461253c661fc7bed4954d634af0a37286207a2d2ebb91cf4d`
- `backtest_n02_walkforward_pg.py`
  - N02 bets: 13
  - stdout SHA-256: `2fabb92986e6e3ba1d37826954f625d2242ac1e060ccb5f94b1a0d5464ada168`
- `backtest_n02_rolling_pg.py`
  - N02 bets: 13
  - stdout SHA-256: `644af07cff830dd5457add8b22a7df576c2c65b61398423f788e97ef2e0dfe14`
- `backtest_n02_time_split_pg.py`
  - N02 bets: 13
  - stdout SHA-256: `33f0ab1a164799cb575bd9cba77765179a69725ff3d35b79c2d6a31b5bd20d46`
- `backtest_n01_n02_diagnostics_pg.py`
  - N01 bets: 25
  - N02 bets: 13
  - stdout SHA-256: `bbf509895835b41b4c9513e03a0ca01bc346ad56bbb23c2a3cb53a89831642f4`
- `backtest_v24_motor2_historical_pg.py`
  - processed races: 4,853
  - stdout SHA-256: `8859a8abdf229376d6ca7b10350b6a16f544d929992d167bd9e54133417dc228`

`PROB_CAL_ARCHIVE_RESULT=PASS_READ_ONLY` was reached only after all six exact-output comparisons passed. The archive was ephemeral and removed before job exit. No Production code, DB row, model, retention rule, or configuration was changed.

### Realtime historical archive export/readback matrix

Run `34970777408` / job `104386249686` proved the same immutable exporter/readback contract on four July `snapshot_label=historical` realtime tables:

- weather: 4,932 rows; canonical payload 20,007,229 bytes; gzip 932,162 bytes
- exhibition: 29,274 rows; canonical payload 15,596,488 bytes; gzip 736,063 bytes
- race condition: 4,932 rows; canonical payload 20,145,500 bytes; gzip 933,764 bytes
- racer condition: 29,592 rows; canonical payload 18,231,834 bytes; gzip 1,176,075 bytes
- total: 68,730 rows; canonical payload 73,981,051 bytes; gzip 3,778,064 bytes

Every manifest had `readback_verified=true`, logical-key duplicate count 0, exact canonical/file SHA-256 verification, and `source_rows_deleted=false`. Combined with the July base-odds file, the five proven July archive files occupy about 11.9 MB on the ephemeral runner. This demonstrates archive feasibility; it is not a retention cutoff or a physical Railway reclaim guarantee.

## Current migration matrix

| consumer / path | role | old-history dependency | migration state |
|---|---|---:|---|
| daily data prepare | live current-day | no | **KEEP ONLINE** |
| v21 safe realtime collector / base fallback | live current-day | no | **KEEP ONLINE** |
| v24 PRE helper | legacy/current-day | no | retire with old PRE; no full-history requirement |
| `run_odds_window_pg.py` | active current-day acquisition | no | **KEEP ONLINE** |
| historical readiness | research/diagnostic | yes | **ARCHIVE EQUIVALENCE PROVEN** |
| Feature Lab | research | yes | **ARCHIVE EQUIVALENCE PROVEN** |
| `analyze_final_ab_features_pg.py` | research | realtime history | **ARCHIVE EQUIVALENCE PROVEN** |
| `compare_motor_boat_ab_pg.py` | historical research | yes | **ARCHIVE EQUIVALENCE PROVEN** |
| `backtest_prob_calibration_pg.py` | historical research | yes | **ARCHIVE EQUIVALENCE PROVEN** |
| `backtest_n02_walkforward_pg.py` | historical research | yes | **ARCHIVE EQUIVALENCE PROVEN** |
| `backtest_n02_rolling_pg.py` | historical research | yes | **ARCHIVE EQUIVALENCE PROVEN** |
| `backtest_n02_time_split_pg.py` | historical research | yes | **ARCHIVE EQUIVALENCE PROVEN** |
| `backtest_n01_n02_diagnostics_pg.py` | historical research | yes | **ARCHIVE EQUIVALENCE PROVEN** |
| `backtest_v24_motor2_historical_pg.py` | historical research | yes | **ARCHIVE EQUIVALENCE PROVEN** |
| `backtest_candidate_filter_rules_pg.py` | historical research | yes | SQL shape compatible; manual research; equivalence pending |
| `backtest_v24_motor2_base_candidate_features_pg.py` | historical research | yes | SQL shape compatible; manual research; equivalence pending |
| `backtest_v24_motor2_low_mid_grid_pg.py` | historical research | yes | SQL shape compatible; manual/heavy research; equivalence intentionally deferred |
| Motor2 transition / mid-veto diagnostics | historical diagnostic | indirect/base odds | pending equivalence-or-retirement review |
| month-gap / repair utilities | maintenance | yes | review archive-aware operation vs obsolete retirement |
| `bao-value-calibration-oos-readonly.yml` manual report | manual research | yes | archive-read-through migration required before old online rows are removed |

Default-branch reference searches for the three SQL-compatible pending backtests above found only the scripts themselves and repository classification, not a scheduled Production workflow entrypoint. They are migration backlog, not evidence that all old history must stay online.

The remaining direct-SQL count is a research/maintenance migration backlog, not evidence that old history must remain in the live Production working set forever.

## Manual research workflow caveat

`.github/workflows/bao-value-calibration-oos-readonly.yml` is manual/issue-comment driven, not a normal Production runtime path, but it still invokes `backtest_prob_calibration_pg.py` against PostgreSQL historical odds. The consumer logic itself has archive equivalence proof, but this workflow must be rewired to verified archive/read-through (or explicitly retired) before any old online base-odds deletion.

## Railway service findings

Two monthly Production services have names that no longer match their actual commands.

### `historical-backfill`

Current start command:

`python -u diagnose_motor2_parser_pg.py`

This is a Motor2 parser diagnostic, not a broad historical odds backfill. It has no persistent DB-write path in the audited script.

### `backtest-analysis`

Current start command:

`python -u collect_v24_motor2_forward_shadow_pg.py`

The current fixed manual/test invocation uses a stable logical conflict key rather than creating an unbounded monthly history. These rows are not Production scoring input. This service remains a separate retirement/hygiene candidate and must not be changed without explicit Production approval.

## Latest retention scenario

Production read-only run `34968032637` measured reference windows as of 2026-09-15.

### `v2_odds_trifecta`

- total: 7,981,493 rows
- logical tuple payload: 830,075,423 bytes
- relation size: 1,844,002,816 bytes
- 30-day reference hot: 545,940 rows / 56,777,757 logical bytes
- 30-day reference cold: 7,435,553 rows / 773,297,666 logical bytes

### realtime odds relation

- relation size: 536,854,528 bytes
- `final_ab` 30-day hot: 498,208 rows / 94,924,296 logical bytes
- `final_ab` 30-day cold: 557,812 rows / 106,331,968 logical bytes
- `learning_all` 30-day hot: 445,565 rows / 84,861,496 logical bytes
- `learning_all` 30-day cold: 22,125 rows / 4,248,000 logical bytes

`30d` is only a capacity reference, **not an approved retention cutoff**. A rough relation-density planning estimate suggests roughly 1.8 GiB of relation-size reduction may be possible across base + realtime history after a fresh logical migration, but this is not a DELETE/VACUUM reclaim promise. Hobby readiness must be judged from an actual fresh restore/migration size plus growth headroom.

## Target archive architecture

### Online Railway PostgreSQL

Keep:

- current-day acquisition and live scoring inputs;
- recent operational evidence required by realtime features;
- V4/Forward provenance and exact decision snapshots;
- results/payout evidence needed for current evaluation;
- enough safety headroom for normal growth and failures.

### External recoverable archive

Keep older raw history needed for:

- backtesting;
- retraining;
- reproducibility;
- audits;
- future model research.

Archive data must not be discarded merely to fit a smaller Railway plan.

## Retention-boundary rule

No rolling-day cutoff is authorized here. A future boundary may be chosen only after:

1. every live Production consumer is mapped;
2. every retained historical consumer has verified archive access or is explicitly retired;
3. permanent archive storage + credentials + restore/readback are proven;
4. correction/reingest and research workflows work against archive evidence;
5. daily growth and safety buffer are measured;
6. a fresh logical migration/restore proves the real database/volume size;
7. the user explicitly approves the Production migration/removal action.

## Current decision

`FULL_HISTORY_NOT_REQUIRED_BY_LIVE_LOADERS / ARCHIVE_EQUIVALENCE_PROVEN_FOR_N02_TIME_SPLIT_AND_DIAGNOSTICS / REALTIME_HISTORICAL_EXPORT_READBACK_PROVEN / MANUAL_RESEARCH_BACKLOG_REMAINS / MANUAL_RESEARCH_WORKFLOW_REWIRE_PENDING / 30D_REFERENCE_ONLY / NO_DELETE / NO_RETENTION_CUTOFF / NO_SERVICE_CHANGE / NO_BUCKET_CREATE`
