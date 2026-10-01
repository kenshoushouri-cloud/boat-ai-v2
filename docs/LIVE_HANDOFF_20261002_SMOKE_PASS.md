# Live Handoff 2026-10-02 — cutover smoke PASS

## 1. SoT / protection
- GitHub `main` = code SoT; always re-fetch live.
- **Production data SoT = `postgres-hobby-fullhistory-candidate-v4`**.
- `postgres-recovery` = protected rollback reference; keep 20GB volume unchanged.
- `postgres-history-archive` = 5GB empty/reserved; do not move history yet.
- retention = **FULL_HISTORY_PINNED**.
- Protect V4/V5 prospective evidence, historical/backtest, TOTO.
- `Postgres` / `Postgres-AbWo` remain unverified: no delete/resize.
- Never call `list_variables`. `purchase_action=false`. One task at a time.

## 2. Cutover state
- final delta sync = PASS.
- zero-delta current exact parity = PASS.
- 13 scheduled DB-connected writers retargeted/redeployed = SUCCESS.
- all scheduled writers remain frozen at `0 0 29 2 *`.
- `test-beforeinfo-extra` retargeted but not manually triggered.
- no cleanup / resize / plan change / purchase action.

## 3. Cutover smoke result
Issue #42 result comment: `5935171451`.

```text
DB_READ=PASS
DB_TEMP_WRITE_ROLLBACK=PASS
DB_WRITABLE=PASS
ODDS_INDEX_VALID_READY=PASS
DB_BYTES=3622991551
PERSISTENT_SMOKE_WRITE=0
PRE_DB_TARGET_MATCH=PASS
FINAL_DB_TARGET_MATCH=PASS
LEARNING_DB_TARGET_MATCH=PASS
PRE_PATH_SMOKE=PASS
FINAL_PATH_SMOKE=PASS
LEARNING_PATH_SMOKE=PASS
SCHEDULE_RESUME=0
DELETE=0
RESIZE=0
PLAN_CHANGE=0
PURCHASE_ACTION=false
CUTOVER_SMOKE=PASS
```

The first smoke attempt failed only because GitHub runner could not resolve Railway private DNS; it made no persistent DB write. The corrected smoke used the candidate public DB endpoint for connectivity and passed.

## 4. Next single task
**Rollback verification.**

Verify that `postgres-recovery` remains intact/readable and that the rollback path is available without switching Production back.

Do not resume schedules, delete/resize legacy resources, move history, change plan, or perform Hobby downgrade in the same task.

If rollback verification passes, next order:
restore/resume schedules against candidate-v4 -> observe operational health -> legacy cleanup -> Pro→Hobby.

`CUTOVER_DONE / SMOKE_PASS / CANDIDATE_V4_SOT / WRITERS_FROZEN / ROLLBACK_VERIFY_NEXT / PURCHASE_FALSE`
