# V5 concise status — 2026-10-26 JST

## User priority and safety
- **Before backtest:** verify all 13 families from **2025-07 through now** for one canonical path/schema/type/content convention and correct source/time semantics. Plan: `docs/V5_202507_TO_CURRENT_STORAGE_UNIFICATION_PLAN_20261026.md`.
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
- New `deploy/conoha/v5_storage_13_family_catalog_readonly_20261026.sql` (commit `9406568e4d7f358362acf0317acb31377fd48484`) queries PG system catalogs only, 13 src/view/stage relation kinds, ordered column schema, PK, relevant date columns, origin marker. **Not yet run**. No user data scans/writes and NOT a period-coverage proof.
- New full-period normalize-first plan is `docs/V5_202507_TO_CURRENT_STORAGE_UNIFICATION_PLAN_20261026.md` (commit `8da0ddeeb52b08d957cf7e9449a5ed7461681ab3`).

## Next ONE task
- Run **catalog-only SQL now**, user submits 13-family diagnostic output. DO NOT equate catalog match to uniform 2025-07+ historical coverage. Identify HOLDs, then plan safe monthly per-family range sampling on stage physical data after existing stage11 sync finishes.
- Only after period/content/provenance gates and safe V5-only normalizations pass, backtest validated as-of periods with bounded sequential low-cost workload. No duplicate timer, no service changes, no arbitrary row rewrites.
