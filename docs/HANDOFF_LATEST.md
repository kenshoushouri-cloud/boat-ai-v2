# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_2340.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current:
- `postgres-recovery` = Production data SoT until explicit cutover
- candidate-v4 final delta sync = PASS
- writers = frozen
- candidate public table counts = 39/39 vs frozen source
- required odds unique index = VALID/READY
- next = read-only zero-delta exact parity
- no cutover / retarget / plan change yet
- retention = FULL_HISTORY_PINNED
- TOTO protected; `Postgres` / `Postgres-AbWo` unverified
- never call `list_variables`; `purchase_action=false`
- one task at a time / short output

`READ_CURRENT_COMPACT / ZERO_DELTA_NEXT / WRITERS_FROZEN / SOURCE_SOT / PURCHASE_FALSE`
