# V5 copy-first gradual cutover (proposal, 2026-10-22 JST)

## Status
**Proposed design only. No DB writes, table copies, service stops, route flags or timer modifications have been performed.** User suggested staging organized V5 copies while old collection continues, then pausing services *after* today's races to reconcile and switch. This is viable in principle and gives rollback flexibility, but is **not safe to commit to tonight without explicit cutover gates**.

## Constraints verified
- ConoHa local `railway` database ~3,447MB (Oct 22), root filesystem 99GB total / 67GB available at audit. Data + indexes + temporary WAL may cause peak storage substantially larger than the source dataset; disk room is a prerequisite, not a guarantee.
- V5 logical `v5_data` currently has 11 VIEWs, `v5_research` 1 VIEW; **no new physical V5 COPY is done**. All views refer to legacy `public.v2_*`. The raw_* physical target names proposed in existing route modules avoid clashing with logical views.
- Known write paths: daily `repair_month_all_pg.py`, midnight `v5/conoha_midnight_results_pg.py`, official K `save_k_day_results_pg.py`, fallback/repair utilities and `v21_realtime_collector_pg.py` via `v5/conoha_realtime_window_pg.py`; some historical research writers. Static hints are not proof of exclusive runtime paths; `pg_schema_compat_v5.py` contains older DDL.
- Existing morning/night, forward-window, midnight-catchup timers can independently start jobs. The result catchup used the 01:20 JST next trigger in prior audit; verify **current** timer status/actual pending results rather than assuming final race time is sufficient to pause.
- Oct 19 encrypted backups are on Google Drive; a few limited ConoHa backups are local. Not all later volatile exhibition/odds captures can be regenerated from official historical pages. Avoid repeated full backups now, but **minimum rollback protection for new/changed rows and settings is required before any irreversible or mixed-state action**.

## Safer target
- Use **same ConoHa PostgreSQL database**, staged **physical** `v5_data.raw_*` / `v5_data.venues` / `v5_data.trifecta_odds`. No extra always-running DB and no full-database blind duplication. Original physical `public.v2_*` continues serving collection until actual cutover.
- Preserve raw/source/snapshot time provenance for V5; what the predictor elects to use is a separate feature gate. Do not delete data just because it is unused for prediction. `v5_research.motor2_legacy_shadow` is historical research, not live predictive input.
- Data eligible for copying is decided table by table from a catalog/preflight and source-quality checks; do not assume all source relations have the same schemas or keys.
- **Offline route tests** pass for parts of daily/realtime/core/K, but the union of read, write, scheduler, reporting, historical/backtest and schema-compat DDL routes remains unaudited. Live flags remain OFF.

## Stages (all independently gated)
1. **Read-only readiness**: run `deploy/conoha/v5_copy_first_preflight_readonly_20261022.sql`; review source/destination relation kinds, sizes, approximate row counts (not proof), FK/triggers, VIEWs and active writer paths. Confirm no conflicting V5 table exists. Check CPU/WAL/disk budget and base-table indexes/dependent objects.
2. **Prepare**: create/test offline copy/catchup tool with explicit source-to-target allowlist, idempotent key behavior, full preservation of raw metadata, guards against split write paths, DB-safe batching/lock timeout, and postcopy row/content verification. Run dry-run before any SQL DDL. New physical tables need equivalent constraints/indexes, owner/grants, sequences, default expressions and trigger/function compatibility. The existing VIEW bindings need explicit dependency handling and cannot be assumed to automatically switch because physical tables exist.
3. **Optional small pilot**: only after approval, stage `public.v2_venues` into `v5_data.venues`, verify identity/key integrity; keep production reads/writes on legacy. Do not set global core route or remove legacy table.
4. **Online copy**: stage necessary V5 tables individually with incremental strategy; do not scan an entire multi-GB source twice casually. Mutable rows require update/delete reconciliation, not merely inserting new IDs. Snapshot alone is not an ongoing sync.
5. **Cutover after collection finished, not simply after last start**: verify all official daily results and catchup complete/PENDING=0, next timer schedule permits a bounded maintenance window; temporarily stop only the affected **timers plus their services/descendant workers**, confirm zero active writes and no other producers. Final deterministic delta reconciliation + source/target parity by primary keys/selected hashes/timestamp ranges; FK/view/schema/ACL and rollback prerequisites. If late, uncertain, or any gate fails, resume legacy untouched and reschedule to an off-day; never force a same-night cutover.
6. **Switch + canary**: after separate explicit approval, atomically apply documented route/env and VIEW changes, keep old writes blocked, verify one controlled non-buy end-to-end collection with valid timing. Ensure no old/new split brain; fallback via documented service/env reversal. Do **not** update the prediction model, auto-purchase, or live ROI labels in this project phase.
7. **Stabilization / backup**: keep old tables protected/read-only for a validation period; after V5 organization/operation tests and restore procedure, make the agreed final encrypted Google Drive backup. Delete legacy only with separate explicit approval.

## STOP rules
No blind `CREATE TABLE AS SELECT` / `LIKE INCLUDING ALL` treated as schema-equality proof; no automatic source DROP; no production flags set by a dry run; no services stopped on a clock-only trigger; no `TRUNCATE` or `CASCADE`. Do not claim 19 Oct backup guarantees all later observational data. No overwrite/hidden unit edits. Limit ConoHa CPU, disk/WAL and Railway usage; avoid overnight gaps.

## Next ONE task
Read-only catalog preflight, no live data change:
```bash
git -C /opt/boat-ai-v5 pull --ff-only &&
runuser -u postgres -- psql -X -v ON_ERROR_STOP=1 -d railway -f /opt/boat-ai-v5/deploy/conoha/v5_copy_first_preflight_readonly_20261022.sql
```
Expect `V5_COPY_FIRST_PREFLIGHT_READONLY_DONE_NO_DB_WRITES`. Investigate any missing source, existing destination, FK, or abnormal sizes before a later COPY pilot.
