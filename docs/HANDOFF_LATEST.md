# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_CLEANUP_PLAN.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current:
- `postgres-hobby-fullhistory-candidate-v4` = Production data SoT
- cutover / smoke / rollback / first resumed Production run = PASS
- active schedules resumed against candidate-v4
- legacy cleanup plan = READY
- Hobby volume limit = 5GB
- oversized blockers:
  - `postgres-recovery` 20GB
  - `Postgres` 50GB, unverified
  - `Postgres-AbWo` 50GB, unverified
- next = read-only verification of `Postgres` / `Postgres-AbWo` through Railway-private path
- no delete / resize / history move / plan change / Hobby downgrade yet
- retention = FULL_HISTORY_PINNED
- TOTO protected
- never call `list_variables`; `purchase_action=false`
- one task at a time / short output

`READ_CURRENT_COMPACT / CLEANUP_PLAN_READY / VERIFY_ORPHANS_NEXT / PURCHASE_FALSE`
