# V5 current compact entry — 2026-10-26 JST

Current handoff: `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`
Only read this index, the current compact and `docs/NEXT_CHAT_START_HERE.md`. Old handoffs/history are reference-only. SHA, row counts and timer status require live recheck.

## Priority change: STORAGE FIRST
User explicitly directs us to verify/fix **all 13 families, 2025-07 through current**, to ONE consistent storage schema/format before backtesting. New gated plan:
`docs/V5_202507_TO_CURRENT_STORAGE_UNIFICATION_PLAN_20261026.md`.
Catalog-only SQL ready:
`deploy/conoha/v5_storage_13_family_catalog_readonly_20261026.sql`.
**Catalog executed 2026-10-26 19:19: 13/13 shape OK; monthly data validity/coverage and repair NOT complete.** Focus subsequent inspection and normalization on **V5 shared stage physical data `boat_data_stage.*` ONLY**; old legacy sources/archives are lineage, not presumed correct, and are not broad cleanup targets. Stage synchronization is not proof of data truth.
Next GitHub SQL: `deploy/conoha/v5_shared_stage_13_index_preflight_readonly_20261026.sql` (catalog-only, not yet run). Then index-safe monthly stage-only audit, V5-only normalization/verification, V5 backtest.

Existing 2026-10-27 03:05 JST stage11 timer untouched; do not create duplicate sync. Current legacy data collectors protected; no DB writes or collector stops, no production cutover, BUY=OFF. Google Drive backups deferred until stable, no old dumps deleted. Railway unused. Aim low CPU/RAM/DB/WAL cost. Night work sequential.
