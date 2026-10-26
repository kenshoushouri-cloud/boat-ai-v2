# V5 Direct Collection (primary) + Legacy Isolated Collection (temporary fallback)
Date: 2026-10-26 JST
STATUS: DESIGN ONLY / NOT DEPLOYED / NO TIMERS OR WRITER FLAGS CHANGED

## Decision proposal
The user proposes to run V5 and old collection in parallel for a temporary transition:
1. V5 fetches official data directly and writes ONLY to canonical physical V5 shared tables (candidate physical target `boat_data_stage.*`, whose table structure must be validated for each writer).
2. Old collector continues to collect to a DISTINCT legacy physical namespace (`public.v2_*` currently), not to the V5 canonical tables.
3. Use old records only to detect and selectively restore missing V5 records, with verified event/race identity, data source, timestamp and original pre-deadline validity. Do not blindly replay post-race observations as predecision snapshots.
4. When V5 direct collector is end-to-end reliable and rollback/restore tested, switch off legacy collection without removing or modifying the old records.

## Verified code facts / blockers
- `v5/conoha_realtime_window_pg.py` spawns `v21_realtime_collector_pg_safe.py`; this is NOT yet an independent V5 collector.
- `v5_daily_table_routes.py` defaults to profile `legacy`; opt-in mappings point to `v5_data.raw_*` candidate tables (not necessarily the actual `boat_data_stage.*` physical V5 common tables). It explicitly warns it redirects only `repair_month_all_pg.py` writes, not nested child collectors or DDL.
- `v5_realtime_table_routes.py` defaults to `legacy` and opts into `v5_data.raw_{weather/exhibition/entry/odds/race_condition/racer_condition}_snapshots`; existing stage uses `boat_data_stage.*`. Catalog/column/key/trigger/default compatibility and concrete runtime writes MUST be checked before enabling anything.
- `v5_core_read_routes.py` defaults reads to `public.v2_*`. Changing only write routing would leave core readers on the old source; must switch verified readers consistently at cutover.
- The 2026-10-26 user's stage QA found 144 race IDs (12 venues × 12 races) with no `boat_data_stage.entries` for the current day. Does not prove whether `public.v2_race_entries` has these records or whether actual prediction consumed the missing stage rows. Source/stage same-day diagnostic was created at `deploy/conoha/v5_today_entries_source_vs_stage_readonly_20261026.sql` but not yet shown executed.
- Existing one-time 2026-10-27 03:05 JST `boat-v5-stage11-delta-20261027-recovery.timer` should remain unchanged and its post-run status independently checked.

## Safe implementation phases (no transition yet)
A. READ ONLY: inventory *all* running entry, race, odds, exhibition, weather, results/catchup writers, timers, cron children, their output destinations and locks. Compare actual same-day source vs stage with a narrow statement-timeout-bounded query. Identify all V5 prediction/read consumers and exact deadline requirements.
B. DESIGN/TEST: create independent V5 official fetch/validation pipeline + explicit physical V5 stage writes; no implicit legacy fallback and no duplicate writer to same table. Preserve original capture time, official race ID, lane, snapshot label, capture request metadata, and update semantics; reject expired race from live-buy route. Unit + integration tests with BUY=OFF and synthetic/offline fixtures.
C. PILOT: one small collection canary on V5 physical target, with old collector still writing ONLY legacy source. Verify each V5 direct record is accurate, on time, and isolated. Use staggered HTTP requests/low traffic to avoid extra official-site load and cost. Monitor CPU, network, locks, WAL, rate limiting.
D. TEMPORARY PARALLEL: V5 primary, legacy secondary and separately persisted. Read-only continuous compare by (race_id, lane) and (race_id, snapshot_label, timestamp/ticket) as applicable, source and deadline. Repair only proven absent V5 rows with provenance-preserving idempotent UPSERT and explicit approval/gate; do not overwrite valid newer records with legacy; no fabricated historical as-of.
E. DECOMMISSION: once all morning/day/night, predeadline odds/exhibition/weather, after-race result and midnight catchup paths are covered, parity and low-error canary pass and rollback/restore confirmed, stop/disable old collectors by audited service/timer list. Keep old data for a hold period. Remove only with separate authorization.

## Invariants
- No premature old collector shutdown; no live split brain or two writers to same canonical relation.
- V5 is sole canonical read target only AFTER real V5 data collection plus quality gates. Old data is a fallback, not an automatic untrusted feature source.
- No destructive DDL, `TRUNCATE`, `DROP`, cron/route switching, new paid resources or purchases without validated independent backup/rollback and approval.
- Synchronization alone is NOT enough for V5 prediction. Required information must exist before its *specific* race cutoff, with capture provenance.
- Avoid 2x traffic bursts, shared flock contention, 5-minute timer gaps and unbounded scans.
- Keep costs minimal, remain on ConoHa, Railway cloud not used.

## Next ONE safe task
Perform the existing small, targeted same-day source-vs-stage READ ONLY check, then a live writer/reader inventory; do NOT activate parallel V5 collection until the independent collector's physical stage routes are built and validated.
