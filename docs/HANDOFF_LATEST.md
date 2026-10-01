# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_ARCHIVE_RESTORE_PASS.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current:
- `postgres-hobby-fullhistory-candidate-v4` = Production data SoT
- cutover / smoke / rollback / first resumed Production run = PASS
- active schedules resumed against candidate-v4
- `Postgres` 50GB = verified logically empty
- `Postgres-AbWo` 50GB = verified logically empty
- fresh encrypted `postgres-recovery` archive + isolated restore = PASS
- restore run `36934788763` = SUCCESS
- oversized Hobby blockers ready for explicit cleanup approval:
  - `Postgres` 50GB
  - `Postgres-AbWo` 50GB
  - `postgres-recovery` 20GB
- next = explicit destructive cleanup approval; remove one at a time with live verification
- do not delete candidate-v4 / archive / escrow-key / active writers / TOTO
- do not change plan in same cleanup task
- never call `list_variables`; `purchase_action=false`
- one task at a time / short output

`READ_CURRENT_COMPACT / ARCHIVE_RESTORE_PASS / EXPLICIT_DELETE_APPROVAL_NEXT / PURCHASE_FALSE`
