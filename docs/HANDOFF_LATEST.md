# V5 current compact entry — 2026-10-26 JST

Current handoff: `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`
Only read this index, the current compact and `docs/NEXT_CHAT_START_HERE.md`. Old handoffs/history are reference-only. SHA, row counts and timer status require live recheck.

## Priority change: STORAGE FIRST
User explicitly directs us to verify/fix **all 13 families, 2025-07 through current**, to ONE consistent storage schema/format before backtesting. New gated plan:
`docs/V5_202507_TO_CURRENT_STORAGE_UNIFICATION_PLAN_20261026.md`.
Catalog-only SQL ready:
`deploy/conoha/v5_storage_13_family_catalog_readonly_20261026.sql`.
**Catalog executed 2026-10-26 19:19: 13/13 shape OK; monthly data validity/coverage and repair NOT complete.** Focus subsequent inspection and normalization on **V5 shared stage physical data `boat_data_stage.*` ONLY**; old legacy sources/archives are lineage, not presumed correct, and are not broad cleanup targets. Stage synchronization is not proof of data truth.
Next GitHub SQL: `deploy/conoha/v5_shared_stage_13_index_preflight_readonly_20261026.sql` (2026-10-26 19:32 JST user screenshot: catalog-only 13 rows, completed; monthly data audit still pending). Next: EXPLAIN-only 2025-07 staged `races` date-filter query plan prepared at `deploy/conoha/v5_shared_stage_races_202507_plan_only_20261026.sql` (GitHub commit `4df5cf0c2c9977f7715c425fcc163a4c37364b08`, NOT EXECUTED). It reads catalog/planner only, not rows. After plan and scheduled sync, index-safe month coverage, V5-only normalization/verification and V5 backtest.

Existing 2026-10-27 03:05 JST stage11 timer untouched; do not create duplicate sync. Current legacy data collectors protected; no DB writes or collector stops, no production cutover, BUY=OFF. Google Drive backups deferred until stable, no old dumps deleted. Railway unused. Aim low CPU/RAM/DB/WAL cost. Night work sequential.

2026-10-26 19:44 JST: stage.races July 2025 EXPLAIN (no ANALYZE) confirmed valid race_date index, Index Only Scan; estimate 5293 NOT actual. 16-month provisional read-only stage.races count SQL prepared at deploy/conoha/v5_shared_stage_races_monthly_readonly_20261026.sql (commit 4bbdd9a6769fb965e0c1c38d8f1ea9dded97d1bd), NOT YET RUN. Pre-sync counts are provisional; scheduled 03:05 sync remains unchanged; no BUY/cutover.

2026-10-26 19:51 JST: user ConoHa screenshot confirmed stage.races 16-month read-only index-count completed July 2025 5196; Aug 5088; Sep 4272; Oct 4152; Nov 3948; Dec 4800; 2026 Jan 5340; Feb 4200; Mar 4692; Apr 4380; May 4896; Jun 4692; Jul 4932; Aug 4932; Sep 4656; Oct 4032 (partial), 16/16 months nonzero. This proves observed rows only; stage copied source may contain errors and sync is due 03:05. Next small stage-only July 2025 race-day QA in deploy/conoha/v5_shared_stage_races_july2025_daily_quality_readonly_20261026.sql (commit bb4ea744c420aa7e4255a0fa988f950537c6e02e), NOT RUN, only indexed one month; no BUY/cutover.

2026-10-26 19:56 JST screenshot: `boat_data_stage.races` July 2025 venue-days=433, race rows=5196, 12-race venue-day anomalies=0, invalid IDs=0, incomplete venue-days=0, `ROLLBACK` success. Internal consistency ONLY; completeness/official as-of proof NOT established. New all-16-month stage-races read-only QA SQL `deploy/conoha/v5_shared_stage_races_16month_quality_readonly_20261026.sql` at `ff435156807022c7163834476e4b8110275be00e` ready, NOT EXECUTED; 5s timeout and one small physical (~19 MB) stage table, no legacy joins. Stage11 03:05 timer untouched; no BUY/cutover.

2026-10-26 20:00 JST user terminal screenshot: stage-only `races` 16-month monthly race-day internal QA completed, 16 rows, `ROLLBACK`, anomalies/invalid IDs=0 in every month; 2026-10 partial and all historical source/as-of still UNVERIFIED. No DB writes. Next task: GitHub-only prepared `deploy/conoha/v5_shared_stage_entries_202507_plan_only_20261026.sql` at commit `ce507dfd56c2b1bfc270e6d5265694271b99ac77`, NOT YET RUN. EXPLAIN-only 2025-07 stage.entries lexical race_id range, index definitions and 6-lane grouping, no user data scans. Hold physical monthly entries scan until indexes and access plan confirmed. 2026-10-27 03:05 stage11 delta timer unchanged, after that check status first; no BUY/cutover.
