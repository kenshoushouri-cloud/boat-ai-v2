# V5 latest active handoff pointer — 2026-10-26 20:16 JST
- Read only `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`, plus `docs/NEXT_CHAT_START_HERE.md` when starting new chat. Avoid old handoff/historical mass reads.
- Objective: V5 common physical `boat_data_stage.*` 13-family schema/2025-07 onward monthly consistency first, then original as-of evidence, then real V5 walk-forward/ROI backtest.
- July 2025: staged races 5196, entries 31176; 5196 races with exactly six unique lanes/racer numbers, no structural holds, 0 race-ID set missing/orphans (20:16 read-only screenshot). Only INTERNAL consistency; stage source truth/as-of unverified. All 16 stage-races monthly 12-race venue-day audits passed internally; remaining 12-family monthly validations pending.
- **Next ONE task:** run reusable bounded stage `races`+`entries` monthly check (`2025-09 3`) at `deploy/conoha/v5_shared_stage_races_entries_monthly_batch_readonly_20261026.sh` commit `e7195fb9f933cb7b9a9840e03f35c4b7e7a51e80` (August passed 20:22 JST; Sep-Nov NOT RUN). Each month 5s timeout, stage-only, no DML. Stop on timeout.
- 2026-10-27 03:05 JST pre-existing one-time 11-family delta timer unchanged; verify completion journal afterward; no parallel sync. Protect 5-min live odds/exhibition/weather collection, no BUY, cutover or backups while unstable. ConoHa local PG DB named `railway`, Railway cloud currently empty per user.

- August 2025 run completed read-only: 5088 races, 5088 entries races, 30528 entry rows, all missing/orphan/invalid lane/identity counts 0. Internal only/source unverified.
