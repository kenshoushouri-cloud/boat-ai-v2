# Live Handoff 2026-10-02 — schedules resumed

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
- 13 scheduled DB-connected writers were retargeted/redeployed to candidate-v4 = SUCCESS.
- `test-beforeinfo-extra` retargeted and remains manual/no cron.

## 3. Production schedules resumed
Issue #42 result comment: `5935457327`.

Live verified original schedules:
- `cron-data-prepare` = `30 21 * * *`
- `cron-final-check` = `*/15 23,0-14 * * *`
- `cron-learning-all` = `*/15 23,0-14 * * *`
- `cron-nightly-results` = `30 14 * * *`
- `cron-window-morning` = `15 23 * * *`
- `cron-window-day` = `35 0 * * *`
- `cron-window-night` = `35 5 * * *`
- `cron-racer-course-stats` = `15 22 * * *`
- `cron-opponent-pressure-v2-live` = `0 22 * * *`
- `backtest-analysis` = `0 0 1 * *`
- `historical-backfill` = `0 0 1 * *`
- `cron-daily-report` = `50 14 * * *`
- `cron-monthly-report` = `0 0 1 * *`
- `test-beforeinfo-extra` = no cron.

13/13 latest deployments remain SUCCESS.
No rollback switch, delete, resize, history move, cleanup, plan change, or Hobby downgrade was performed in this task.

## 4. Next single task
**Operational health observation against candidate-v4 after schedule resume.**

Verify the first resumed Production runs, DB growth/headroom, and absence of new failures before cleanup or plan change.

Do not delete/resize legacy resources, move history, or downgrade plan in the same task.

If health is good, next order:
legacy cleanup planning -> Pro→Hobby.

`CUTOVER_DONE / SMOKE_PASS / ROLLBACK_PASS / SCHEDULES_RESUMED / HEALTH_OBSERVE_NEXT / PURCHASE_FALSE`
