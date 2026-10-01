# Live Handoff 2026-10-02 — first resumed Production run PASS

## 1. SoT / protection
- GitHub `main` = code SoT; always re-fetch live.
- **Production data SoT = `postgres-hobby-fullhistory-candidate-v4`**.
- `postgres-recovery` = verified rollback reference; keep 20GB volume unchanged.
- `postgres-history-archive` = 5GB empty/reserved; do not move history yet.
- retention = **FULL_HISTORY_PINNED**.
- Protect V4/V5 prospective evidence, historical/backtest, TOTO.
- `Postgres` / `Postgres-AbWo` remain unverified: no delete/resize.
- Never call `list_variables`. `purchase_action=false`. One task at a time.

## 2. Migration state
- final delta sync = PASS.
- zero-delta exact parity = PASS.
- explicit cutover to candidate-v4 = DONE.
- cutover smoke = PASS.
- rollback verification = PASS.
- 13 scheduled DB-connected writers = original schedules resumed against candidate-v4.
- `test-beforeinfo-extra` remains manual/no cron.

## 3. First resumed Production run
Issue #42 result comment: `5941563305`.

`cron-data-prepare`:
- started 2026-10-02 06:31 JST.
- race/base processing = 288/288, failed=0.
- daily odds quality audit reached.
- complete_races=0.
- pending_races=164.
- problem_races=4.
- partial_odds=4.
- missing_odds=0.
- invalid_ticket=0.
- unexpected=0.
- non-final morning preparation stage; pending/partial rows are not a hard failure.

Post-run candidate-v4:
- disk usage = `4.352606208 GB / 5 GB`.
- approximate remaining headroom = `0.647393792 GB`.
- new FAILED deployments = 0.
- new CRASHED deployments = 0.
- error/fatal/panic/no-space/OOM-like logs = 0.

Operational health gate after schedule resume = PASS.

## 4. Next single task
**Legacy cleanup planning before Pro→Hobby.**

Plan only first. Do not delete/resize `postgres-recovery`, TOTO, unverified `Postgres` / `Postgres-AbWo`, or move FULL_HISTORY_PINNED history without explicit verification.

Do not perform Hobby downgrade in the same task unless the cleanup plan shows no blocker and the user explicitly continues.

`CUTOVER_DONE / SMOKE_PASS / ROLLBACK_PASS / SCHEDULES_RESUMED / FIRST_RUN_PASS / LEGACY_CLEANUP_PLAN_NEXT / PURCHASE_FALSE`
