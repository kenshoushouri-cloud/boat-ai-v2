# V5 current compact pointer — 2026-10-26 20:12 JST
- Active handoff: `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`
- Historical common-data normalization plan: `docs/V5_202507_TO_CURRENT_STORAGE_UNIFICATION_PLAN_20261026.md`
- July 2025 stage.races 5,196; stage.entries 31,176 and per-race 6-lane/unique racer structural checks all PASS (20:12 screenshot). Not source verified. 16/16 monthly stage.races internal day/race-number checks pass.
- **Next ONE task:** execute read-only July 2025 stage.races vs stage.entries race-ID set equality SQL at `deploy/conoha/v5_shared_stage_races_entries_202507_race_id_set_readonly_20261026.sql` commit `a093c0c8fc76adf9900151bfc58fe038948208b6`, NOT RUN yet. 5-second cap, stop on timeout.
- Stage11 guarded night sync timer due 2026-10-27 03:05 JST untouched. 13-family data completeness, original predeadline timing, ROI backtest, V5 live cutover all pending. BUY OFF. Old sources may be inaccurate and must not be blindly trusted/rewritten. No backup expansion until stable. ConoHa local PostgreSQL database named `railway`, NOT Railway cloud platform. Keep collector active, low CPU/RAM/DB load.
- Read only latest compact and next-chat-start guide; do not bulk load old handoffs.
