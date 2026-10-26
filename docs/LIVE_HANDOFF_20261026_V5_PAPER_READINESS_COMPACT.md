# V5 concise operational status — 2026-10-26 20:44 JST
## Goal and fixed boundaries
- V5 main system: verify/correct **13 shared physical `boat_data_stage.*` families** 2025-07 onward, unify schema/semantics, prove predeadline timestamps, then real walk-forward ROI backtest; continue research capture. Old `public.v2_*` copies are lineage only, not presumed accurate, and `boat_data.*` are legacy-backed VIEWs, not cleansed V5 tables. No old data mass scans or cleanup.
- ConoHa local PostgreSQL database is named `railway` (NOT active Railway cloud). Keep costs/CPU/RAM/WAL low. No Railway service/Agent, no production cutover, BUY OFF.
- Keep all existing odds/exhibition/weather collectors and their 5-min cadence. No system reboot. User deferred expanded backups until stable; no deletion/overwrite without restore.
- **Already scheduled** one-time stage11 delta at **2026-10-27 03:05 JST**: `boat-v5-stage11-delta-20261027-recovery.timer`. Do NOT launch parallel copy or edit its schedule; after execution inspect journal and verify staged table parity. The guarded staging script `deploy/conoha/v5_stage12_delta_reconcile_guarded_20261025.py` has 03:00–05:44 JST write window for remaining 11.
- Safeguards: old mutable data/late ingestion cannot be called original as-of. Keep unverifiable snapshots or features HOLD, not fabricated ROI. Existing synthetic tests 18+17 pass but not real-backtest proof.

## Data verified so far (ConoHa read-only screenshots, 2026-10-26)
- All **13/13 stage-family catalog shapes, PKs, mapped relations** passed; stage-only index/date metadata preflight returned 13 rows. These do not prove row content or full month completeness.
- `boat_data_stage.races`: 2025-07 to 2026-10 **16 months** have data and internally valid venue/day 12-race structure / race date & number ID shape (0 detected errors); October partial. Not checked against official complete event calendar.
- `boat_data_stage.entries`: 146MB; index `entries_race_id_idx` and unique `entries_race_id_lane_key` valid. Date prefix ranges query-indexed; tested read-only batch script at commit `e7195fb9f933cb7b9a9840e03f35c4b7e7a51e80` takes `YYYY-MM [1..3]`, per-month 5s statement/500ms lock limit, work_mem=4MB, checks stage race-ID equality plus 6 unique lanes/racer numbers. Results, all 4 mismatch counters **0**, `ROLLBACK`, `INTERNAL_OK_STAGE_ONLY_SOURCE_UNVERIFIED`:
  - 2025-07: 5,196 races / 31,176 entries (additional independent ID set/6-lane diagnostics)
  - 2025-08: 5,088 / 30,528
  - 2025-09: 4,272 / 25,632
  - 2025-10: 4,152 / 24,912
  - 2025-11: 3,948 / 23,688
  - 2025-12: 4,800 / 28,800
  - 2026-01: 5,340 / 32,040
  - 2026-02: 4,200 / 25,200
  - 2026-03: 4,692 / 28,152
  - 2026-04: 4,380 / 26,280
  - 2026-05: 4,896 / 29,376
  - 2026-06: 4,692 / 28,152
  - 2026-07: 4,932 / 29,592
  - 2026-08: 4,932 / 29,592
- 2026-06 to 2026-08 tested at 20:41 JST: three rows complete, each races_missing_entries=0, orphan_entry_races=0, invalid_lane_races=0, invalid_racer_races=0; read-only ROLLBACK. **15/16 months stage races↔entries internally checked PASS** (September 2026 4,656 races / 27,936 entries, all four counters zero); **October is HOLD** (4,032 stage races / 3,888 entry race IDs / 23,328 entry rows, 144 races missing all entries; other three counters zero), and other 11 families NOT certified. Passing months have NO independent official completeness/correctness or historical predeadline capture verification.

## Next ONE task
- Run same **existing tested stage-only** script with the October missing-entry day/venue diagnostic, then recheck after nightly guarded delta sequentially; stop on any timeout, avoid increased load or duplicate runs. Continue small batches only after verification. Post-night-delta, check service status and refreshed shared data before final claim. Backtest only after all 13 family coverage/normalization and as-of criteria satisfied.

## 2026-10-26 20:44 JST — October discrepancy, do NOT promote to PASS
- User terminal `2026-09 2` completed both read-only queries, ROLLBACK. September: `race_rows=4656, entry_races=4656, entry_rows=27936, races_missing_entries=0, orphan_entry_races=0, invalid_lane_races=0, invalid_racer_races=0` => PASS internal. October: `race_rows=4032, entry_races=3888, entry_rows=23328, races_missing_entries=144, orphan_entry_races=0, invalid_lane_races=0, invalid_racer_races=0` => `HOLD_STAGE_RACE_ENTRY_MISMATCH`. Batch completion footer is not a PASS verdict. Stage copy lag, uncollected entries, future race dates, or other causes are possible and not yet proven.
- **Next ONE task:** read-only index-bounded diagnostic `deploy/conoha/v5_shared_stage_oct2026_missing_entries_by_day_venue_readonly_20261026.sql` pinned `b72f215c719e4a58d189802d1b557d05b81abec3`, NOT RUN. Groups missing entry race IDs by `race_date,venue_code` and race numbers; 5s SQL + 500ms lock timeout; no source scans, writes or timer edits. Stop on timeout.
- Existing stage11 one-time 2026-10-27 03:05 JST sync is unchanged. Check its journal/result and repeat hold check afterwards; only after proof, decide whether targeted repair in V5 shared stage is needed. Do not blind-copy unverified legacy values. 2026-10 partial, BUY OFF/cutover off.
