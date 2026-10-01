# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_HOBBY_ACTIVE.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current:
- `postgres-hobby-fullhistory-candidate-v4` = Production data SoT
- migration / restore / oversized cleanup = complete
- Railway Active Plan = Hobby
- boat-v2-postgres post-Hobby smoke = PASS
- TOTO post-Hobby smoke = PASS
- first unambiguous post-Hobby scheduled run at 08:30 JST = PASS
- next = read-only candidate-v4 storage safety check
- protect candidate-v4 / history archive / escrow key / active writers / TOTO
- never call `list_variables`; `purchase_action=false`
- one task at a time / short output

`READ_CURRENT_COMPACT / HOBBY_ACTIVE / STORAGE_SAFETY_NEXT / PURCHASE_FALSE`
