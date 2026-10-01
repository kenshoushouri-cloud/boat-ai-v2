# Live Handoff 2026-10-02 — recovery archive restore PASS

## 1. SoT / protection
- GitHub `main` = code SoT; always re-fetch live.
- **Production data SoT = `postgres-hobby-fullhistory-candidate-v4`**.
- `postgres-recovery` = rollback reference; now freshly archived and restore-verified.
- `postgres-history-archive` = 5GB reserved; FULL_HISTORY_PINNED history not moved yet.
- Protect V4/V5 prospective evidence, historical/backtest, TOTO.
- Never call `list_variables`. `purchase_action=false`. One task at a time.

## 2. Production migration health
- cutover = DONE.
- cutover smoke = PASS.
- rollback verification = PASS.
- 13 scheduled writers resumed against candidate-v4.
- first resumed Production run = PASS.
- candidate-v4 post-run disk ~= 4.3526 GB / 5 GB.

## 3. Oversized orphan verification
- `Postgres` 50GB: logical DB ~7.86MB, 0 public tables/indexes, no boat tables.
- `Postgres-AbWo` 50GB: logical DB ~7.86MB, 0 public tables/indexes, no boat tables.
- Both verified read-only with DB_WRITE=0.
- No current Production writer dependency remains on either service.

## 4. Fresh postgres-recovery archive + isolated restore
GitHub Actions run: `36934788763` = **SUCCESS**.
Issue #42 result comment: `5941919741`.

Result:
- fresh source dump created read-only.
- encrypted artifact = `boat-ai-pre-hobby-restorable-20261001-v2`.
- plain dump bytes = `303,976,040`.
- dump SHA-256 = `4022c52a7df31dc01cc54b66e06eec144778831b1358d5fc645c5785855bd35b`.
- restored SHA-256 = exact match.
- restore-list entries = `272`.
- isolated restored DB bytes = `3,630,438,079`.
- public tables = `39`.
- exact row-count parity passed for:
  - `v2_races`
  - `v2_race_entries`
  - `v2_results`
  - `v2_result_entries`
- escrow key remains in `archive-restore-key-20261001`; key value was never printed/uploaded.
- SOURCE_WRITE=0.
- no Production row/schema mutation.
- older archive remains retained as historical evidence.

## 5. Hobby blockers now
Railway Hobby volume limit = 5GB.

Oversized blockers:
- `postgres-recovery` = 20GB allocated; rollback contents now fresh archive + restore verified.
- `Postgres` = 50GB allocated; verified logically empty.
- `Postgres-AbWo` = 50GB allocated; verified logically empty.

These oversized volumes cannot be shrunk in place; Railway resizing expands only.

## 6. Next single task
**Explicit destructive cleanup of the three oversized Hobby blockers, only after user approval.**

Proposed removals:
1. `Postgres` + 50GB volume — verified empty.
2. `Postgres-AbWo` + 50GB volume — verified empty.
3. `postgres-recovery` + 20GB rollback volume — only because fresh encrypted archive + isolated restore verification passed and Production is candidate-v4.

Before deletion, re-fetch live status/dependencies once. Delete one resource at a time and verify after each.

Do NOT delete:
- candidate-v4 Production.
- postgres-history-archive.
- archive-restore-key-20261001.
- active writer/report/backtest/historical services.
- TOTO.
- FULL_HISTORY_PINNED data.

Do not change Railway plan in the same cleanup task.

After cleanup verification:
**Hobby compatibility check -> Pro→Hobby plan change.**

`RECOVERY_ARCHIVE_RESTORE_PASS / THREE_OVERSIZED_DELETE_CANDIDATES / EXPLICIT_DELETE_APPROVAL_NEXT / PURCHASE_FALSE`
