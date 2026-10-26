# V5 latest — 2026-10-26 20:27 JST
Current compact: `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`
Reference scope: `docs/V5_202507_TO_CURRENT_STORAGE_UNIFICATION_PLAN_20261026.md`

Priority: 13 V5 shared physical `boat_data_stage.*` families 2025-07 onward; consistent schema, monthly internal QA, then independent source/as-of proof, then real V5 backtest. Old sources are NOT presumed correct.
2025-07 to 2025-11: stage `races` ↔ `entries` month-by-month ID-set, 6 lanes, 6 racer identities passed. 2025-09/10/11 20:27 JST terminal result: 4272/4152/3948 races, 25632/24912/23688 entries, four hold counters all zero; `ROLLBACK`. Stage internal integrity only, source not verified. Stage `races` race/day checks pass for 16 months, other families remain incomplete.
**Next ONE task:** run 3 months `2025-12 3` (Dec 2025–Feb 2026) using `deploy/conoha/v5_shared_stage_races_entries_monthly_batch_readonly_20261026.sh` at tested commit `e7195fb9f933cb7b9a9840e03f35c4b7e7a51e80`. One stage-only READ ONLY DB query per month, 5s timeout; stop on errors, no retry bursts.
Existing ConoHa stage11 sync timer 2026-10-27 03:05 JST preserved, no duplicate. Protect data collectors. BUY=OFF, no cutover or destructive changes. Backup expansion deferred. ConoHa local PG database is named `railway`, not active Railway cloud. For new chat read only compact/current and `docs/NEXT_CHAT_START_HERE.md`; no historical bulk reads.
