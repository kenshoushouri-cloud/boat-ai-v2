# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_FIRST_RUN_PASS.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current:
- `postgres-hobby-fullhistory-candidate-v4` = Production data SoT
- `postgres-recovery` = verified rollback reference with preserved 20GB volume
- cutover / smoke / rollback verification = PASS
- 13 scheduled writers = original schedules resumed against candidate-v4
- first resumed Production run = PASS
- post-run candidate disk = 4.352606208 GB / 5 GB
- FAILED/CRASHED since run window = 0
- next = legacy cleanup planning before Pro→Hobby
- no cleanup / resize / history move / plan change / Hobby downgrade yet
- retention = FULL_HISTORY_PINNED
- TOTO protected; `Postgres` / `Postgres-AbWo` unverified
- never call `list_variables`; `purchase_action=false`
- one task at a time / short output

`READ_CURRENT_COMPACT / FIRST_RUN_PASS / LEGACY_CLEANUP_PLAN_NEXT / PURCHASE_FALSE`
