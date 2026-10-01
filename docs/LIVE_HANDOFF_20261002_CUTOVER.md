# Live Handoff 2026-10-02 — candidate-v4 cutover

## 1. SoT / protection
- GitHub `main` = code SoT; always re-fetch live.
- **Production data SoT = `postgres-hobby-fullhistory-candidate-v4`** after explicit cutover.
- `postgres-recovery` = rollback reference; keep unchanged with 20GB volume.
- `postgres-history-archive` remains empty/reserved; do not move history yet.
- retention = **FULL_HISTORY_PINNED**.
- Protect V4/V5 prospective evidence, historical/backtest, TOTO.
- `Postgres` / `Postgres-AbWo` remain unverified: no delete/resize.
- Never call `list_variables`. `purchase_action=false`. One task at a time.

## 2. Cutover evidence
- frozen-source final delta sync = PASS.
- read-only current exact parity = PASS; `MISMATCH_KINDS=NONE`.
- parity result comment: Issue #42 comment `5933962737`.
- candidate logical DB at parity: `3,622,991,551 bytes`.
- candidate Railway disk immediately before cutover: about `4.352 GB / 5 GB`.
- 13 scheduled DB-connected writer services were redeployed after retarget; all reached `SUCCESS`.
- all 13 remain frozen at cron `0 0 29 2 *`.
- `test-beforeinfo-extra`: DATABASE_URL retargeted, not redeployed/manual-run.
- no delete, resize, plan change, cleanup, or purchase action.

## 3. Current state
- Production writer configuration now resolves to candidate-v4.
- `postgres-recovery` remains rollback-only and protected.
- schedules are still frozen; Production jobs have not been resumed.
- no smoke test has been run after cutover yet.

## 4. Next single task
**Run cutover smoke test against candidate-v4 while schedules remain frozen.**

Do not resume schedules, delete/resize legacy resources, change plan, or clean up in the same task.

If smoke passes, next order:
rollback verification -> restore/resume schedules against candidate-v4 -> observe -> legacy cleanup -> Pro→Hobby.

`CUTOVER_DONE / CANDIDATE_V4_SOT / WRITERS_FROZEN / SMOKE_NEXT / ROLLBACK_PROTECTED / PURCHASE_FALSE`
