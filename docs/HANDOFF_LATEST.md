# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_ROLLBACK_PASS.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current:
- `postgres-hobby-fullhistory-candidate-v4` = Production data SoT
- `postgres-recovery` = verified rollback reference with preserved 20GB volume
- final delta sync = PASS
- zero-delta exact parity = PASS
- explicit cutover = DONE
- cutover smoke = PASS
- rollback verification = PASS
- writers remain frozen
- next = restore/resume original writer schedules against candidate-v4
- no cleanup / resize / history move / plan change / Hobby downgrade yet
- retention = FULL_HISTORY_PINNED
- TOTO protected; `Postgres` / `Postgres-AbWo` unverified
- never call `list_variables`; `purchase_action=false`
- one task at a time / short output

`READ_CURRENT_COMPACT / ROLLBACK_PASS / RESUME_SCHEDULES_NEXT / PURCHASE_FALSE`
