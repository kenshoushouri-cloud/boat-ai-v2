# Live Handoff 2026-10-02 — oversized orphan DBs verified

## 1. SoT / protection
- GitHub `main` = code SoT; always re-fetch live.
- **Production data SoT = `postgres-hobby-fullhistory-candidate-v4`**.
- `postgres-recovery` = verified rollback reference until freshly archived/retired.
- `postgres-history-archive` = 5GB reserved; do not move FULL_HISTORY_PINNED data yet.
- Protect V4/V5 prospective evidence, historical/backtest, TOTO.
- Never call `list_variables`. `purchase_action=false`. One task at a time.

## 2. Production migration health
- cutover = DONE.
- cutover smoke = PASS.
- rollback verification = PASS.
- 13 scheduled writers resumed against candidate-v4.
- first resumed Production run = PASS.
- candidate-v4 post-run disk ~= 4.3526 GB / 5 GB.
- no new FAILED / CRASHED / no-space / OOM at health gate.

## 3. Hobby blockers / verification
Railway Hobby volume limit = 5GB.

Oversized services:
- `postgres-recovery`: 20GB allocated, actual disk ~4.990GB; verified rollback source.
- `Postgres`: 50GB allocated.
- `Postgres-AbWo`: 50GB allocated.

Issue #42 verification comment: `5941844199`.

Railway-private read-only inspection:
### Postgres
- logical current DB = railway.
- DB_BYTES = 7,861,951.
- PUBLIC_TABLES = 0.
- PUBLIC_INDEXES = 0.
- HAS_V2_RACES = false.
- HAS_V2_RESULTS = false.
- DB_WRITE=0.

### Postgres-AbWo
- logical current DB = railway.
- DB_BYTES = 7,861,951.
- PUBLIC_TABLES = 0.
- PUBLIC_INDEXES = 0.
- HAS_V2_RACES = false.
- HAS_V2_RESULTS = false.
- DB_WRITE=0.

Conclusion:
- both 50GB services are empty PostgreSQL shells from the logical-data perspective, not boat Production/history DBs.
- no `Postgres-AbWo.DATABASE_URL` repo reference found.
- matches for `Postgres.DATABASE_URL` are legacy/lowercase `postgres` compatibility references; current Production writers are already on candidate-v4.
- the temporary legacy audit service was returned to candidate-v4 reference without deploy and set restart policy NEVER; no verification dependency remains on the oversized DBs.

No delete / resize / history move / plan change / Hobby downgrade was performed.

## 4. Next single task
**Create a fresh encrypted read-only archive of `postgres-recovery` and restore-verify it before destructive cleanup.**

Use the existing isolated restore-drill path. Preserve the escrow key. Do not delete/resize any DB in the same task.

If fresh archive + restore verification passes, the next step is explicit destructive cleanup approval for the oversized blockers.

`ORPHAN_DBS_VERIFIED_EMPTY / RECOVERY_ARCHIVE_NEXT / NO_DELETE_YET / PURCHASE_FALSE`
