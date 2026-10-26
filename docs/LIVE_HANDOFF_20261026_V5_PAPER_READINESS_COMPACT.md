# V5 compact operational handoff — 2026-10-26 20:47 JST

## Purpose and guardrails
- V5 primary model. Validate/normalize 13 shared physical `boat_data_stage.*` families covering 2025-07 onward before factual/as-of checks and walk-forward ROI backtest. Existing legacy `public.v2_*` and `boat_data.*` VIEW records may be inaccurate; a stage copy is not verification of truth.
- Use ConoHa local PostgreSQL DB **named `railway`** (not Railway cloud); user says Railway cloud empty. Keep CPU/RAM/WAL/network expense low; no Railway Agent/AI. BUY=OFF, no cutover or test buys. Keep existing collectors (odds/exhibition/weather) and timers uninterrupted; do not reboot.
- User deferred expanded backup work until stable. No deletion, overwrite, or blind legacy repair. If historical capture-before-deadline evidence is absent, hold feature/buy instead of inventing results.
- Keep this handoff compact. Old handoffs only for needed specific details.

## Timeline and nighttime sync
- Existing one-time systemd timer `boat-v5-stage11-delta-20261027-recovery.timer` set for **2026-10-27 03:05 JST** per prior user terminal screenshot. Do not start extra daytime/parallel sync or edit timer. **Run completion is NOT yet confirmed.**
- GitHub `deploy/conoha/v5_stage12_delta_reconcile_guarded_20261025.py` has 12 family mappings and `--remaining` (11 excluding `races`) **includes `public.v2_race_entries → boat_data_stage.entries`**. Overnight guarded write window 03:00–05:44 JST; actual per-family success must be established from journal, not presumed. This sync reflects source state but cannot prove original value/as-of correctness.

## Stage-only user screenshot results (2026-10-26)
- 13/13 families catalog/PK mapped; this is schema only, not a full 13-family temporal or content audit.
- Stage `races` 2025-07–2026-10 (16 months) has internally well-formed twelve-race venue-days and checked race-ID date/number shape, no detected internal anomalies. October is partial; real-world race coverage unverified.
- Stage `races ↔ entries` monthly batch `deploy/conoha/v5_shared_stage_races_entries_monthly_batch_readonly_20261026.sh` at commit `e7195fb9f933cb7b9a9840e03f35c4b7e7a51e80` is tested read-only with 5s per-month timeout and `YYYY-MM [1..3]` args; it checks race-ID set, six unique lanes and distinct racer numbers. **15 months 2025-07 through 2026-09 PASS INTERNAL ONLY**, all four mismatch counters zero; 2026-09 stage races 4656, entry race IDs 4656, entry rows 27936.
- **2026-10 HOLD**, user 20:44 screenshot: stage races 4032, entry race IDs 3888, entry rows 23328, **144 races with no entries** (0 orphan entry race IDs, 0 invalid-lane and racer-race groups); read-only ROLLBACK.
- User 20:47 diagnostic screenshot using `deploy/conoha/v5_shared_stage_oct2026_missing_entries_by_day_venue_readonly_20261026.sql`: **all 144 missing entry-race IDs occur only on 2026-10-26**, across **12 venues × 12 races each (1R–12R)**. No older October date displayed. Most likely stage freshness lag but **not proven** whether source rows already exist. Do NOT invent 864 missing source rows (864 would be the expected stage entry-row count if all six per race), and do not blindly backfill.
- Remaining 11 shared families still require safe period and content QA; provenance and ROI remain unverified.

## Next ONE task
- **After 2026-10-27 03:05 JST**, first read-only check unit journal for `boat-v5-stage11-delta-20261027-recovery.service` and `DELTA_TABLE_COMMITTED entries` or any `HOLD_...`, then re-run previously tested **`2026-10 1`** stage monthly read-only QA script and see if October's `races_missing_entries` becomes 0. If timer fails or missing remains, diagnose source/stage for **2026-10-26 only**, plan safe targeted remedy after proof. Never assume night sync finished just because scheduled.
- No other writes, parallel sync, BUY, cutover, or 13-family full scans before this checkpoint.
