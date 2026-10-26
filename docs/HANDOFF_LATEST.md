# V5 active handoff pointer — 2026-10-26 20:33 JST
Read current compact: `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`. Main plan: `docs/V5_202507_TO_CURRENT_STORAGE_UNIFICATION_PLAN_20261026.md`. Avoid old handoff bulk reads.
Goal: audit/normalize all 13 V5 common physical stage families 2025-07 onward; source truth & predeadline as-of checks before backtest.
Current screenshot: 2026-03/04/05 staged races↔entries PASS (4,692/4,380/4,896 races, 28,152/26,280/29,376 entries, missing/orphan/invalid lane/identity=0 per month). Now 2025-07–2026-05 **11/16 consecutive months** with internal races/entries QC pass; copied source still unverified. Other 11 families unverified.
**Next ONE task:** run pre-tested `deploy/conoha/v5_shared_stage_races_entries_monthly_batch_readonly_20261026.sh` at commit `e7195fb9f933cb7b9a9840e03f35c4b7e7a51e80` with `2026-06 3` (June–August); 3 serial read-only 5s-capped monthly queries. STOP on timeout.
Existing ConoHa 2026-10-27 03:05 JST stage11 delta timer unchanged, result pending. No duplicate sync, no BUY, collector stops, V5 cutover, Railway usage, backup changes or destructive ops. DB `railway` is local on ConoHa.
