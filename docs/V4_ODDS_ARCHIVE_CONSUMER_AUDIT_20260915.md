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

## Historical consumers still blocking archive-only storage

Default-branch code still contains historical consumers that assume older odds are directly queryable from PostgreSQL. Examples include:

- historical/backtest feature analysis;
- historical month gap/repair checks;
- backtest readiness/diagnostic utilities;
- feature laboratory / model-comparison utilities;
- historical odds-window research.

These tools are valuable and should not simply lose data access. They must either:

1. be migrated to an external archive/read-through interface; or
2. be explicitly retired as obsolete after dependency review.

Until then, deleting old online odds rows would break legitimate research/reproducibility workflows.

## Railway service findings

Two monthly Production services have names that no longer match their actual commands:

### `historical-backfill`

Current start command:

`python -u diagnose_motor2_parser_pg.py`

The script is a Motor2 parser diagnostic over `v2_race_entries` plus official-page fetches. It does not function as a broad historical odds backfill.

### `backtest-analysis`

Current start command:

`python -u collect_v24_motor2_forward_shadow_pg.py`

The script uses target-date/current-day semantics and writes the Motor2 shadow table. It is not a general historical backtest job.

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

`FULL_HISTORY_NOT_REQUIRED_BY_KEY_LIVE_ODDS_LOADERS / HISTORICAL_CONSUMERS_STILL_BLOCK_OFFLOAD / ARCHIVE_READ_THROUGH_DESIGN_NEXT / NO_DELETE / NO_RETENTION_CUTOFF / NO_SERVICE_CHANGE`
