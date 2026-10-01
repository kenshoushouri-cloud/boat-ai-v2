# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_ORPHANS_VERIFIED.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current:
- `postgres-hobby-fullhistory-candidate-v4` = Production data SoT
- cutover / smoke / rollback / first resumed Production run = PASS
- active schedules resumed against candidate-v4
- oversized orphan DB verification = PASS
- `Postgres` 50GB = logical DB ~7.86MB, 0 public tables/indexes, no boat tables
- `Postgres-AbWo` 50GB = logical DB ~7.86MB, 0 public tables/indexes, no boat tables
- `postgres-recovery` 20GB remains protected rollback source
- next = fresh encrypted read-only archive + isolated restore verification of `postgres-recovery`
- no delete / resize / history move / plan change / Hobby downgrade yet
- retention = FULL_HISTORY_PINNED
- TOTO protected
- never call `list_variables`; `purchase_action=false`
- one task at a time / short output

`READ_CURRENT_COMPACT / ORPHAN_DBS_VERIFIED_EMPTY / RECOVERY_ARCHIVE_NEXT / PURCHASE_FALSE`
