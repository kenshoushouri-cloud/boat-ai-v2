# V5 compact operational handoff — 2026-10-26 20:08 JST

## Goal / current priority
- V5 is main model. First **verify and normalize the 13 shared-data families** (2025-07 through current) in one consistent staging schema, **then** validate original point-in-time provenance and backtest for predictive performance and ROI. Do not use predictive-degrading features simply because present; continue collecting research data.
- Only `boat_data_stage.*` **physical V5 common data** is the current cleanup/audit target. `boat_data.*` objects are legacy-backed VIEWs, not an independently cleaned final V5 store. Old `public.v2_*` and separate archive are lineage only and may be inaccurate; do not scan/repair all old systems. Stage delta is copying, **not** evidence that contents are correct. Full stage normalization/cutover remains incomplete. Detailed plan: `docs/V5_202507_TO_CURRENT_STORAGE_UNIFICATION_PLAN_20261026.md`.

## Hard safeguards
- ConoHa local PostgreSQL database name `railway` (this does NOT mean data on Railway cloud). User says Railway cloud has no current data; do not connect or spend there. Prefer GitHub-only edits and short read-only ConoHa validation; CPU/RAM/network/WAL and costs minimal, no Railway AI/Agent.
- Keep existing collectors (including odds/exhibition/weather) and service timers uninterrupted. No production cutover, no BUY (BUY=OFF). Do not reboot ConoHa despite OS restart banner.
- An already scheduled one-time systemd `boat-v5-stage11-delta-20261027-recovery.timer` is due **2026-10-27 03:05 JST**. Remaining 11 staged tables can be updated only in 03:00–05:44 window by `deploy/conoha/v5_stage12_delta_reconcile_guarded_20261025.py`. No duplicate or forced daytime sync. Its actual post-run success is UNKNOWN until journal checked after schedule.
- User postponed further backup work until V5 stable; retain existing backups, no destructive deletes/overwrites without restore protection. Never repurpose mutable historical `created_at`/`updated_at` as proof of original pre-deadline capture; make unusable data HOLD, not fabricated ROI.
- Keep chats/tools concise (one task at a time), handoff concise; do not bulk-read old handoffs.

## Verified by user ConoHa screenshots, 2026-10-26
- Synthetic V5 quality 18/18 and revised offline VIEW identity adapter 17/17 PASS; tests are NOT real full-model ROI/backtest.
- Six-row `boat_data.entries` historical/VIEW sample `20261026_10_01`: six populated `racer_number`, six legacy `racer_no` SQL NULL; all 13 selected stats non-NULL, not verified numeric values/time provenance. Separate detailed live VIEW range SQL timed out after 5s; avoid heavy daytime live VIEW scans.
- 13/13 family **catalog schema, primary-key and source/stage relation shape** passed `CATALOG_SHAPE_OK_PERIOD_NOT_AUDITED` at 19:19. All 13 staged family index/date metadata candidates enumerated at 19:32. Catalog alignment is not monthly data/completeness proof.
- Physical stage `races`: B-tree `races_race_date_idx`, `Index Only Scan` plan. 16 monthly actual stage row counts 2025-07 to 2026-10 all nonzero; October current month partial. Physical stage **race-day structural QA** for all 16 months completed at 20:00: every month has 0 unusual 12-race venue-days and 0 malformed date/race number IDs; **not** official full-event/source proof.
- Physical stage `entries`: 146MB, `entries_race_id_idx` and unique `entries_race_id_lane_key` valid+ready; July 2025 EXPLAIN count `Index Only Scan` and per-race group `Index Scan` (not executed by EXPLAIN). At **20:08**, July 2025 actual count `31,176`, equal to 5,196 stage races × 6, read-only ROLLBACK. **Total equality is insufficient to prove six unique lanes per race, distinct identities, matched race IDs, or truth.**

## Next ONE task (prepared, NOT RUN)
- GitHub file `deploy/conoha/v5_shared_stage_entries_202507_lane_quality_readonly_20261026.sql`, commit `c1dbd4834ecd7d77d14336fc2faef39b12f458c1`: read-only capped 5s, stage entries only, July 2025 `race_id` indexed range, per-race count(6), distinct lane 6, min/max lane 1..6, distinct `racer_number` 6, null/invalid number count. No legacy joins and no production writes. STOP if timeout, don't increase time budget.
- After success consider independent stage race-id set matching with race-date (to catch orphan/missing whole races) before rolling out to all months. Index-appropriate month cohorts for remaining 11+ family types only AFTER stage11 sync proof. No unproven as-of feature backtests.
