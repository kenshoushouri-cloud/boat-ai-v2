# Live Handoff — 2026-10-01 17:10 JST (compact)

Status: **CURRENT COMPACT HANDOFF**  
Repository: `kenshoushouri-cloud/boat-ai-v2`

Always re-fetch live state. SHA/run/count values below are observations, not fixed constants.

## 1. Fixed contract

- GitHub `main` = code Source of Truth
- Railway `postgres-recovery` = Production data Source of Truth
- 2026-09-29 formal V4 = permanently **UNAVAILABLE**
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days + S03_M2 >=100 official observations + clean evidence contract
- historical reconstruction gives zero prospective gate credit
- `purchase_action=false`
- retention = **FULL_HISTORY_PINNED**
- protect V4/V5/backtest/historical collection data
- never enumerate plaintext Railway Variables / never call `list_variables`
- Railway Agent = exceptional fallback only; prefer normal MCP
- Production behavior/cutover/delete/resize/plan changes require explicit approval

## 2. Schedule

Daily: `08:15 cutoff -> 08:16 GitHub -> 08:20 Railway fallback -> formal freeze -> 23:30 settlement`

Migration:
- **2026-10-02:** target to complete Production -> Hobby cutover/downgrade
- **2026-10-03:** billing renewal boundary; do not wait until this date to migrate
- around **2026-10-15:** V5 operational-readiness review target; not automatic go-live

Last settled research snapshot remains V4 **8/20** and S03_M2 **63/100** until live settlement evidence says otherwise.

## 3. Protected Production / research path

Keep:
- `postgres-recovery` + 20 GB volume; Railway volume cannot be shrunk in place
- `historical-backfill`, `backtest-analysis`
- Production cron paths including `cron-final-check`, `cron-learning-all`
- V4/V5 evidence/artifacts and prospective collection
- candidate-v3 as temporary rollback reference until final cutover accepted

Backtest/V4/V5 data currently depends on `postgres-recovery`; do not delete it before verified cutover.

## 4. 5 GB candidate-v4

Service: `postgres-hobby-fullhistory-candidate-v4`.

Established:
- fixed artifact `36812386066` exact parity previously PASS
- current-source refresh restored a fresh read-only `postgres-recovery` snapshot into v4 successfully
- large odds index is present after rebuild:
  `ux_v2_odds_trifecta_race_ticket` about **303 MB**
- latest direct footprint observation:
  - DB **3,596,662,463 bytes**
  - WAL **536,870,912 bytes**
  - public index bytes about **919 MB**
  - `max_wal_size=512MB`
  - Railway disk about **4.34 GB / 5 GB**
- Production source logical DB observed about **4.45 GB**; compact restore removes physical bloat

Current-source parity immediately after refresh is expected to drift while Production collectors continue writing. Last read-only comparison showed schema parity and only table-count deltas across 8 tables, total **572 rows**. Do not chase exact live parity with repeated full restores while writers remain active.

The refresh run's final validation falsely failed because psql meta commands were double-escaped. The index itself was created successfully. Main commit `aaf924e2...` fixes that workflow validation.

## 5. Cleanup state

Deletion is only **staged**, not applied, because Railway requires dashboard 2FA.

Staged obsolete resources include old Hobby migration candidates/workers and isolated legacy Postgres resources. Approx. volume allocation staged for removal: **160 GB**.

**Do not Apply staged changes yet** until final safety review. Protected `postgres-recovery`, v3, v4, historical/backtest, and active cron paths are not deletion targets.

## 6. Next safe order

1. read-only final-cutover preflight: identify exact writer services to freeze
2. obtain explicit approval for the short Production write-freeze / final sync window
3. during freeze, run fixed v4 current refresh once
4. require snapshot exact parity and then live current parity with zero delta
5. explicit cutover approval
6. switch DB references / smoke test
7. only after stable cutover: Apply approved cleanup and Pro -> Hobby downgrade before 2026-10-03 billing boundary

No historical DELETE, Production cutover, volume resize/delete, or plan change before the required approval.

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / FULL_HISTORY_PINNED / PROTECT_BACKTEST / 5GB_V4 / FINAL_SYNC_BEFORE_CUTOVER / PURCHASE_FALSE`
