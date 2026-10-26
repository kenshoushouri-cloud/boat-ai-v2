# V5 concise status — 2026-10-26 JST

## User priority and safety
- **Before backtest:** verify all 13 V5 **shared physical stage** families from **2025-07 through now** (master venues is version-based), by consistent path/schema/type/content and correct source/time semantics. Plan: `docs/V5_202507_TO_CURRENT_STORAGE_UNIFICATION_PLAN_20261026.md`.
- ConoHa `railway` (local Postgres) + GitHub only; Railway has no current data per user, no need to connect.
- Original public.v2_* data & live collectors preserved. Current `boat_data.*` = legacy-reading VIEWs, `boat_data_stage.*` = isolated physical copies. LIVE writer cutover = NO_GO, BUY=OFF. Do not alter live timers, stop collector, run concurrent sync, or reboot.
- Google Drive/new backup work postponed by user until stable operation; retain all existing backups, never delete or destructively rewrite while restore is unverified.
- Target 2025-07+ research; do not treat late-loaded mutable odds, exhibition, stats, or created_at/updated_at as immutable original pre-deadline captures. Missing value != weak racer and NULL != zero. As-of/data leak audit prerequisite before any valid ROI claim.

## Confirmed environment / progress
- 10/26 17:17 screenshot: stage11 one-time timer `boat-v5-stage11-delta-20261027-recovery.timer` active, next **2026-10-27 03:05 JST**. Status/result AFTER 03:05 still unverified. Pilot stage `races` previously copied; remaining 11 delta staged tables are scheduled. Snapshot is not continuous CDC. No double run.
- 10/26 GitHub-only V5 synthetic tests: 18/18 quality, then revised 17/17 VIEW adapter; total **35 current synthetic tests PASS** by user ConoHa screenshots, no actual V5 real-data inference or ROI proof.
- 10/26 read-only six-row real VIEW diagnostic `race_id=20261026_10_01`: 6 lanes, 6 distinct `racer_number` (4189,4872,3441,4442,4113,4273), `racer_no` SQL NULL in all; 13 checked statistic columns non-NULL for all six. This does NOT prove valid numeric ranges, trustworthy capture timing or other races/months. Revised synthetic VIEW adapter tolerates absent legacy alias as shape only, BUY still HOLD.
- Subsequent six-row stats range query against live VIEW timed out at 5s on 10/26 18:50; not a numerical validation result. Avoid daytime heavy LIVE VIEW scans.

## Checked GitHub storage contract
- `boat_shared_storage_contract.RELATIONS`: fixed **13** legacy `public.v2_*` → logical `boat_data.*` VIEW mapping. Stage uses `boat_data_stage.*` physical copies; the original venues stage is protected. A separate `boat_history_archive` DB exists and is NOT identical to the live DB.
- `deploy/conoha/v5_stage12_delta_reconcile_guarded_20261025.py`: 11 remaining tables allowed only 03:00–05:44 JST; per-table REPEATABLE READ/PK windows/verify/rollback and staged writes only. Full-history V5 model/ROI engine is NOT yet validated, so overnight all-period backtest must not run blindly.
- New `deploy/conoha/v5_storage_13_family_catalog_readonly_20261026.sql` (commit `9406568e4d7f358362acf0317acb31377fd48484`) queries PG system catalogs only, 13 src/view/stage relation kinds, ordered column schema, PK, relevant date columns, origin marker. **Executed 2026-10-26 19:19 JST: 13/13 structural catalog pass**, NOT a period-coverage proof. No user data scans/writes.
- New full-period normalize-first plan is `docs/V5_202507_TO_CURRENT_STORAGE_UNIFICATION_PLAN_20261026.md` (commit `8da0ddeeb52b08d957cf7e9449a5ed7461681ab3`).

## 2026-10-26 19:19 JST user screenshot / scope correction
- **13/13** routes returned `CATALOG_SHAPE_OK_PERIOD_NOT_AUDITED` with relation kinds `r|v|r`, matching column counts and PK. ROLLBACK / read-only success marker. An earlier separate SQL attempt timed out; successful subsequent command supersedes only catalog validation, not monthly audit.
- User explicitly prefers **V5 common/shared data ONLY**; legacy V3/V4 data may be inaccurate. Do not broadly repair/scan legacy `public.v2_*` or separate archives. Current shared PHYSICAL dataset is `boat_data_stage.*`, current logical `boat_data.*` still legacy-reading VIEWs (not independently clean). Scheduled stage delta is just copy/reconciliation, not truth repair.
- Newly created stage-only, catalog-only index/date preflight `deploy/conoha/v5_shared_stage_13_index_preflight_readonly_20261026.sql` commit `4ef869f0536e9dcc12d85e45a430a2e5c18a6eba`. It has NOT RUN. Stage monthly full-history checks depend on time-index suitability; do not scan unindexed large relations during collectors.

## Next ONE task
- Run/read stage-only **index/date catalog preflight** (no user table scans). Use its result to design low-cost 2025-07 onward staged per-month audit after the already scheduled 2026-10-27 03:05 stage delta. Repair only V5 normalized layer with independent source proof, never overwrite immutable evidence/old raw rows. No duplicate timer, service changes, BUY or cutover.
