# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_PRE_RUN_HEALTH.md`

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
- post-resume pre-run health baseline = PASS
- candidate disk = 4.352188416 GB / 5 GB, flat at checkpoint
- FAILED/CRASHED since resume = 0
- next = verify first resumed scheduled Production run + post-run headroom
- no cleanup / resize / history move / plan change / Hobby downgrade yet
- retention = FULL_HISTORY_PINNED
- TOTO protected; `Postgres` / `Postgres-AbWo` unverified
- never call `list_variables`; `purchase_action=false`
- one task at a time / short output

`READ_CURRENT_COMPACT / PRE_RUN_HEALTH_PASS / FIRST_RUN_VERIFY_NEXT / PURCHASE_FALSE`
