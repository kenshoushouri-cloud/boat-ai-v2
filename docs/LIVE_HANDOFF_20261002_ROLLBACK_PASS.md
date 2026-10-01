# Live Handoff 2026-10-02 — rollback verification PASS

## 1. SoT / protection
- GitHub `main` = code SoT; always re-fetch live.
- **Production data SoT = `postgres-hobby-fullhistory-candidate-v4`**.
- `postgres-recovery` = verified rollback reference; 20GB volume preserved.
- `postgres-history-archive` = 5GB empty/reserved; do not move history yet.
- retention = **FULL_HISTORY_PINNED**.
- Protect V4/V5 prospective evidence, historical/backtest, TOTO.
- `Postgres` / `Postgres-AbWo` remain unverified: no delete/resize.
- Never call `list_variables`. `purchase_action=false`. One task at a time.

## 2. Cutover / smoke
- final delta sync = PASS.
- zero-delta exact parity before cutover = PASS.
- explicit cutover to candidate-v4 = DONE.
- 13 scheduled DB-connected writers retargeted/redeployed = SUCCESS.
- cutover smoke = PASS.
- PRE / FINAL / learning target + path smoke = PASS.
- all scheduled writers remain frozen at `0 0 29 2 *`.
- `test-beforeinfo-extra` retargeted but not manually triggered.

## 3. Rollback verification
Railway live:
- `postgres-recovery` deployment = SUCCESS.
- preserved volume = `postgres-volume`, 20GB, attached at `/var/lib/postgresql/data`.

Issue #42 result comment: `5935397125`.

```text
SOURCE_STABLE_DURING_AUDIT=true
CANDIDATE_MATCHES_SOURCE_BEFORE=true
CANDIDATE_MATCHES_SOURCE_AFTER=true
SOURCE_BEFORE_DB_BYTES=4460189375
SOURCE_AFTER_DB_BYTES=4460189375
CANDIDATE_DB_BYTES=3622991551
CANDIDATE_HEADROOM_BYTES=1377008449
UNDER_5GB=true
MISMATCH_KINDS=NONE
CURRENT_EXACT_PARITY=PASS
SOURCE_WRITE=0
CANDIDATE_WRITE=0
CUTOVER=0
DELETE=0
RESIZE=0
PLAN_CHANGE=0
PURCHASE_ACTION=false
```

Rollback source and new Production are still exact data-equivalent at the frozen cutover point. No rollback switch was performed.

## 4. Next single task
**Restore/resume the scheduled writer crons against candidate-v4 using their original schedules.**

Keep `postgres-recovery` unchanged as rollback reference.
Do not delete/resize legacy resources, move history, change plan, or perform Hobby downgrade in the same task.

After schedules are restored, next order:
operational health observation -> legacy cleanup planning -> Pro→Hobby.

`CUTOVER_DONE / SMOKE_PASS / ROLLBACK_PASS / CANDIDATE_V4_SOT / RESUME_SCHEDULES_NEXT / PURCHASE_FALSE`
