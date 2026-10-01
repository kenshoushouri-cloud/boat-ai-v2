# Live Handoff 2026-10-02 — post-resume health baseline

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

## 3. Post-resume health baseline
Issue #42 result comment: `5940803226`.

- candidate-v4 deployment = SUCCESS.
- live disk usage = `4.352188416 GB / 5 GB`.
- last 6h disk usage = flat.
- CPU/memory baseline = normal/low.
- FAILED deployments since schedule resume = 0.
- CRASHED deployments since schedule resume = 0.
- candidate DB error/fatal/panic/no-space/OOM logs since resume = 0.
- all 13 original cron schedules remain restored.
- Railway cron is UTC.

At this checkpoint, the first resumed scheduled Production run has not yet occurred. Do not treat the post-resume operational health gate as complete until that run is verified and DB headroom is checked afterward.

## 4. Next single task
**Verify the first resumed scheduled Production run and post-run candidate-v4 disk/headroom.**

Do not delete/resize legacy resources, move history, change plan, or perform Hobby downgrade until this check passes.

If healthy, next order:
legacy cleanup planning -> Pro→Hobby.

`CUTOVER_DONE / SMOKE_PASS / ROLLBACK_PASS / SCHEDULES_RESUMED / PRE_RUN_HEALTH_PASS / FIRST_RUN_VERIFY_NEXT / PURCHASE_FALSE`
