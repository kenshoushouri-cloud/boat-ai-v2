# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_TWO_ORPHANS_DELETED.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current:
- `postgres-hobby-fullhistory-candidate-v4` = Production data SoT
- cutover / smoke / rollback / first resumed Production run = PASS
- active schedules resumed against candidate-v4
- fresh encrypted recovery archive + isolated restore = PASS
- `Postgres` service deleted; 50GB volume pending deletion
- `Postgres-AbWo` service deleted; 50GB volume pending deletion
- `postgres-recovery` 20GB remains the final oversized blocker
- next = final live preflight + delete `postgres-recovery` service/volume under existing explicit cleanup approval
- after that = Hobby compatibility check -> Pro→Hobby
- do not touch candidate-v4 / history archive / escrow key / active writers / TOTO
- never call `list_variables`; `purchase_action=false`
- one task at a time / short output

`READ_CURRENT_COMPACT / TWO_50GB_ORPHANS_DELETED / RECOVERY_20GB_NEXT / PURCHASE_FALSE`
