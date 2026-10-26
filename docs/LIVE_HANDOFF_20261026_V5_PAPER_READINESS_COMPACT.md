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
- Newly created stage-only, catalog-only index/date preflight `deploy/conoha/v5_shared_stage_13_index_preflight_readonly_20261026.sql` commit `4ef869f0536e9dcc12d85e45a430a2e5c18a6eba`. User executed 2026-10-26 19:32 JST: 13 rows and read-only completion marker; screenshot only shows the lower rows. Stage monthly full-history checks depend on time-index suitability; do not scan unindexed large relations during collectors.

## 2026-10-26 19:32 JST — shared-stage preflight confirmed
- ConoHa screenshot: 13 rows, ROLLBACK, V5_SHARED_13_INDEX_PREFLIGHT_COMPLETE_READ_ONLY_CATALOG_ONLY_NO_MONTHLY_SCAN_BUY_OFF. Lower visible rows: race_id-leading index candidate for trifecta_odds (1826 MB), odds_snapshots (779 MB), racer_results (256 MB), weather_snapshots (191 MB), race_condition_snapshots (60 MB), racer_condition_snapshots (72 MB); date-leading candidate for racer_course_stats_snapshots (89 MB), races (19 MB), results (32 MB); venues (48 KB) master. Top rows for entries/entry_snapshots/exhibition_snapshots cut off in screenshot; do not infer classifications.
- Candidate indexes are not proved execution plans, period-by-period data coverage, value correctness, or original pre-deadline capture. Shared stage can contain inaccurate old copies.

## 2026-10-26 evening GitHub-only preparation
- Added `deploy/conoha/v5_shared_stage_races_202507_plan_only_20261026.sql` at commit `4df5cf0c2c9977f7715c425fcc163a4c37364b08`. READ ONLY 4s + lock 500ms; catalogs `boat_data_stage.races` index definitions and `EXPLAIN (ANALYZE FALSE)` one month, 2025-07. **No count query execution, no table scan, no writes**; no claim of monthly coverage. NOT YET EXECUTED.
- This checks whether the planner intends index/heap scan. Even if it shows index usage, actual runtime and month data quality remain unverified. If Seq Scan appears, HOLD and redesign, do not force month scan.

## Next ONE task
- Run/inspect EXPLAIN-only stage `races` 2025-07 plan while live data capture remains untouched. This is a catalog/planner task and does NOT require waiting for scheduled delta.
- Keep existing stage11 2026-10-27 03:05 JST timer unchanged; after it actually finishes, inspect service journal read-only before real row-level month checks; no duplicate sync, production cutover, BUY or backup changes.

## 2026-10-26 19:44 JST latest
Screenshot confirmed `boat_data_stage.races` 2025-07 EXPLAIN-only query used valid `races_race_date_idx` Index Only Scan; estimated ~5293, not real count. New read-only 5s capped monthly count SQL July 2025 through Oct 2026 in `deploy/conoha/v5_shared_stage_races_monthly_readonly_20261026.sql`, commit `4bbdd9a6769fb965e0c1c38d8f1ea9dded97d1bd`, NOT YET EXECUTED. It checks only physical common stage races, not old public source. Before 03:05 delta, counts are provisional, and other 12-family monthly validation remains pending. Current next task is execute/check this bounded provisional count if desired; no additional timer, BUY, backtest or production cutover.

## 2026-10-26 19:51 JST stage.races month counts
ConoHa read-only 16-month query completed and ROLLBACK, 16 rows; observed stage physical races by month: 2025-07=5196, 08=5088, 09=4272, 10=4152, 11=3948, 12=4800; 2026-01=5340, 02=4200, 03=4692, 04=4380, 05=4896, 06=4692, 07=4932, 08=4932, 09=4656, 10=4032 (CURRENT_MONTH_PARTIAL). Each month nonzero but all counts carry STAGE_COUNT_NOT_YET_PROVEN_COMPLETE; not proof of full venue-day coverage, correctness or independent as-of. Stage11 timer remains untouched for 10/27 03:05.
Next ONE task: optional bounded stage-only quality SQL for ONE month July 2025, 5-second timeout, grouped by venue/date and checking 12 races/unique numbered races and race_id date format. `deploy/conoha/v5_shared_stage_races_july2025_daily_quality_readonly_20261026.sql` (commit bb4ea744c420aa7e4255a0fa988f950537c6e02e), NOT RUN. If timeout, stop. Maintain deferred actual 13-family month audit until safe indices and stage11 successful, no production writes/BUY/cutover.
