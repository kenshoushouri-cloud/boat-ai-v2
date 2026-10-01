# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_SMOKE_PASS.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current:
- `postgres-hobby-fullhistory-candidate-v4` = Production data SoT
- `postgres-recovery` = protected rollback reference
- final delta sync = PASS
- zero-delta exact parity = PASS
- explicit cutover = DONE
- cutover smoke = PASS
- PRE / FINAL / learning DB target + path smoke = PASS
- writers remain frozen
- next = rollback verification only
- no cleanup / resize / plan change / Hobby downgrade yet
- retention = FULL_HISTORY_PINNED
- TOTO protected; `Postgres` / `Postgres-AbWo` unverified
- never call `list_variables`; `purchase_action=false`
- one task at a time / short output

`READ_CURRENT_COMPACT / SMOKE_PASS / ROLLBACK_VERIFY_NEXT / WRITERS_FROZEN / PURCHASE_FALSE`
