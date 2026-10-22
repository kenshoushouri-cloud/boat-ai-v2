# 2026-10-23 02:00 JST: One-shot guarded shared-table staging (not cutover)

## Goal
User urgently requests to copy everything and run V5 before ending today's terminal session. **Current verified reality:** ConoHa `railway.boat_data` exists but is empty; `v5_data.venues` holds the previously verified 24-row pilot. Public `v2_*` is STILL the live data used by old V5 collector/writer paths, including midnight 01:20 catchup, 07:00 morning and forward collection, 23:00 night. 29 isolated route tests have passed, but **no complete runtime reader/writer switch certification has passed**. Automated production cutover in this state would jeopardize current capture.

## Safest useful unattended step
The one-shot systemd job starts **2026-10-23 02:00 JST** after 01:20 result catchup; no manual interaction needed once scheduled. It attempts to stage the 13 primary source tables (including 24-row `venues`) into physical `boat_data.*`. Each table uses a single repeatable-read transaction with direct `INSERT ... SELECT` and exact within-snapshot row count equality, commits only a whole table, or rolls it back. Manifest `boat_data._copy_manifest` records committed tables for next-run identification. Live SERIAL/IDENTITY/GENERATED defaults are intentionally NOT copied, to avoid sharing old production sequences; they must be migrated before any live write cutover. FKs, user triggers, writer permissions, stale live deltas and SQL paths **are not certified** by staging.

On ConoHa Termius root, **only after verifying this fixed-date window is still in the future**, paste:

```bash
git -C /opt/boat-ai-v5 pull --ff-only &&
bash /opt/boat-ai-v5/deploy/conoha/boat_shared_bulk_schedule_once_20261023.sh
```

The wrapper first runs local offline tests and a read-only catalogue/disk preview. If any candidate source is missing or disk insufficient, it stops without scheduling anything. Otherwise creates a one-time transient timer `boat-shared-bulk-stage-20261023.timer` due 02:00 JST. CPUQuota 40%, idle IO priority, 1.5GB per-unit memory cap; PostgreSQL's own process and WAL are **not** bounded by that unit. Copy attempts only 02:00–06:15 JST and per-query timeouts prevent starting the 07:00 collection window in the middle of new transactions. It is allowed to fail closed and leave a subset of *fully committed* table snapshots; full migration is not promised. No Railway or external charge.

## Next-night read-only review
```bash
systemctl status boat-shared-bulk-stage-20261023.service --no-pager
journalctl -u boat-shared-bulk-stage-20261023.service -n 100 --no-pager
```
Expected if all 13 succeed: `BULK_STAGING_COMPLETE new=13 earlier=0 NO_PRODUCTION_CUTOVER_NO_SOURCE_DELETES` (may have fewer if aborted). Error `GUARDED_BULK_STAGE_STOP` means no retry or cleanup until inspected. Inspect `boat_data._copy_manifest` row counts. `boat_history_archive` three physical historical tables (1069MB) remain separate with V5 future read-only as-of adapter; do NOT duplicate 1GB blindly.

## Remaining cutover prerequisites, absolutely mandatory
1. Exact post-copy incremental catch-up including newly inserted/updated/removed legacy rows under temporary **verified** writer quiescence, then source/destination parity not just approximate count.
2. Restore serial/identity/defaults, FK, trigger, privilege, index and schema-qualified SQL contract equivalence. Run queries and unit/integration tests including old hardcoded public paths.
3. Identify & control 4 systemd timers and all dynamically spawned collector child writers including K result lane writes. Backtest 2025-07 onwards, predecision capture times and skipped rows no leakage.
4. Only then, coordinated activation of shared-data read/write targets and collection/forecast (non-purchase canary) and tested immediate rollback path.
5. **Delete old source only AFTER** full cutover and restore-tested backup of post-Oct19 irrecoverable predeadline snapshots. Do not claim normal V5 production uses physical `boat_data` until proved.

### Important safety language
- `STAGING_SCHEDULED` is **only timer registration**, not a successful data copy.
- `BULK_STAGING_COMPLETE` is **only point-in-time copy**, not same-second parity after legacy writers continue, nor V5 common-data operation.
- The assistant cannot access ConoHa's shell directly; the operator runs the one command. No guarantee of successful unattended completion, since live schema and runtime resources can change.
