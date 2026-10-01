# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_CUTOVER.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current:
- `postgres-hobby-fullhistory-candidate-v4` = Production data SoT after explicit cutover
- `postgres-recovery` = protected rollback reference
- final delta sync = PASS
- zero-delta current exact parity = PASS
- 13 scheduled DB writers retargeted/redeployed = SUCCESS
- writers remain frozen
- `test-beforeinfo-extra` retargeted but not manually triggered
- next = cutover smoke test while frozen
- no cleanup / resize / plan change yet
- retention = FULL_HISTORY_PINNED
- TOTO protected; `Postgres` / `Postgres-AbWo` unverified
- never call `list_variables`; `purchase_action=false`
- one task at a time / short output

`READ_CURRENT_COMPACT / CUTOVER_DONE / SMOKE_NEXT / WRITERS_FROZEN / ROLLBACK_PROTECTED / PURCHASE_FALSE`
