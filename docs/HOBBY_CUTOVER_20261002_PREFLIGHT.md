# Hobby Cutover Preflight — 2026-10-02

Purpose: complete Pro -> Hobby migration before the 2026-10-03 billing renewal boundary without losing V4/V5/backtest/historical evidence.

## Non-negotiable protection

- Production data Source of Truth remains `postgres-recovery` until cutover is explicitly approved and verified.
- Keep the 20 GB `postgres-recovery` volume. Railway volume shrink is not an in-place migration path.
- Keep V4/V5 prospective evidence, S03_M2 evidence, backtest/historical collection, and candidate-v3 rollback reference.
- `purchase_action=false`.
- Do not call Railway `list_variables`.
- Avoid Railway Agent; normal MCP/GitHub bridge first.
- Do not Apply currently staged deletions before stable cutover verification.

## Candidate-v4 state

- Service: `postgres-hobby-fullhistory-candidate-v4`
- Fresh current-source snapshot restore succeeded.
- Deferred `ux_v2_odds_trifecta_race_ticket` rebuild succeeded physically.
- Direct read-only footprint after refresh:
  - DB about 3.597 GB
  - WAL about 0.537 GB
  - Railway disk about 4.34 GB / 5 GB
  - `max_wal_size=512MB`
- Latest live-source parity difference after refresh was data-count only: 8 tables / 572 rows.
- The difference is expected because `postgres-recovery` continued receiving Production rows after the refresh snapshot.
- Refresh workflow validation bug was only a psql meta-command escaping error and is fixed on main by `aaf924e2...`.

## Services to quiesce for the final sync window

Conservative rule: during final sync, temporarily stop all scheduled/manual jobs below that carry `DATABASE_URL`, so the source stays frozen while v4 is refreshed and verified.

- `cron-data-prepare`
- `cron-final-check`
- `cron-learning-all`
- `cron-nightly-results`
- `cron-window-morning`
- `cron-window-day`
- `cron-window-night`
- `cron-racer-course-stats`
- `cron-opponent-pressure-v2-live`
- `backtest-analysis`
- `historical-backfill`
- `cron-daily-report`
- `cron-monthly-report`
- ensure manual `test-beforeinfo-extra` is not triggered during the window

This freeze is a Production behavior change and therefore requires explicit approval before execution.

## Final sync / cutover sequence

1. Re-fetch live main, Railway status, candidate-v4 disk, and staged changes.
2. Confirm no unrelated migration/candidate workflow is running.
3. With explicit approval, quiesce the DB-connected scheduled/manual jobs above.
4. Verify source is stable with two read-only captures.
5. Run the fixed `candidate-v4 current refresh` once.
6. Require snapshot exact parity: all 39 public table counts + schema metadata + indexes.
7. Run current-source parity while source remains frozen; require zero delta.
8. Require actual Railway candidate disk < 5 GB; abort if operational headroom is unsafe.
9. With explicit cutover approval, redirect Production DB references to candidate-v4.
10. Smoke test DB read/write and core PRE/FINAL/learning paths.
11. Resume scheduled jobs against the new Production DB.
12. Keep `postgres-recovery` and candidate-v3 unchanged as rollback references during observation.
13. Only after stable verification: Apply approved cleanup and perform Pro -> Hobby downgrade.

## Abort conditions

Abort cutover and keep Pro/`postgres-recovery` if any of these occurs:
- candidate-v4 >= 5 GB or unsafe remaining headroom
- schema/index parity mismatch
- table-count mismatch while source is frozen
- failed core smoke test
- any uncertainty about V4/V5/backtest/historical evidence preservation

`PROTECT_PRODUCTION / PROTECT_BACKTEST / FREEZE_THEN_SYNC / ZERO_DELTA_BEFORE_CUTOVER / KEEP_ROLLBACK / HOBBY_BY_2026-10-02`
