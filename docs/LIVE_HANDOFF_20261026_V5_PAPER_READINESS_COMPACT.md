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

## 2026-10-26 20:16 JST: July V5 races/entries crosscheck PASS
- User screenshot from read-only ConoHa query shows `stage_races=5196, distinct_entry_races=5196, races_without_entries=0, entry_races_without_race=0`; SQL ROLLBACK and read-only footer. Combined with 20:12 stage.entries 5196 groups/31176 rows/0 lane or racer structural holds, confirms July V5 physical shared records match internally. Does NOT verify original data truth, all real-world races, or as-of captures.
- New reusable read-only batch `deploy/conoha/v5_shared_stage_races_entries_monthly_batch_readonly_20261026.sh` at commit `e7195fb9f933cb7b9a9840e03f35c4b7e7a51e80`: `YYYY-MM [1..3]` starting month; per-month `BEGIN READ ONLY` PostgreSQL statement_timeout=5s lock_timeout=500ms work_mem=4MB, stage physical `races` and `entries` only, indexed date/race-ID ranges, full outer race-ID set and each race's six lanes and six distinct racer numbers; early halt on SQL timeout/error. NO source/legacy scans, writes, BUY or timer changes. **RUN for 2025-08 on 2026-10-26 20:22 JST; later months NOT RUN**.
- 2025-08 first test PASS (user 20:22 JST screenshot): `race_rows=5088`, `entry_races=5088`, `entry_rows=30528`, all four `races_missing_entries`, `orphan_entry_races`, `invalid_lane_races`, `invalid_racer_races` = 0, verdict `INTERNAL_OK_STAGE_ONLY_SOURCE_UNVERIFIED`, `ROLLBACK`. Next ONE task: run 3 months `2025-09 3` (Sep-Nov 2025) sequentially and review before continuing. If TIMEOUT, STOP. Keep 03:05 scheduled sync untouched. All pre-sync results provisional. Afterwards check delta service journal before claiming 13-family readiness.

## 2026-10-26 20:27 JST new screenshot: Sep-Nov stage QA PASS
- Sequential shared physical stage `races` ↔ `entries` per-month (source unverified) completed with `ROLLBACK`:
  - 2025-09 4,272 races, 25,632 entries;
  - 2025-10 4,152 races, 24,912 entries;
  - 2025-11 3,948 races, 23,688 entries.
- Each month: `races_missing_entries=0`, `orphan_entry_races=0`, `invalid_lane_races=0`, `invalid_racer_races=0`; terminal `V5_STAGE_MONTH_BATCH_COMPLETE_READ_ONLY_PROVISIONAL_NO_WRITES_NO_BUY`.
- Together with July and August results, 2025-07–11 (5 months) have staged internal race/entry ID-and-six-lane checks PASS, **not** official completeness/value truth or proof of first pre-deadline capture. No extra sync or DB writes performed by checks.
- **Next ONE task:** `2025-12 3` (2025 Dec, 2026 Jan-Feb), same GitHub read-only script `deploy/conoha/v5_shared_stage_races_entries_monthly_batch_readonly_20261026.sh`, commit `e7195fb9f933cb7b9a9840e03f35c4b7e7a51e80`; per-month 5s timeout; if one times out stop; after night delta re-check data.
