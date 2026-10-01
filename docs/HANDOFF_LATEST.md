# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_STARTUP_REFRESH.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs/deep-history docs by default. Re-fetch only the live state needed for the next single task.

Source of Truth:
- GitHub `main` = code
- Railway PostgreSQL Production = data

Current focus:
- preserve daily prospective evidence
- let writer `36703692641` finish; no duplicate beforeinfo trigger
- prepare Pro -> Hobby for the 10/03 billing boundary
- backup + encrypted logical archive are secured
- **next task = isolated restore drill**
- restore -> parity -> cutover -> cleanup; never delete first
- V5 operational-readiness target remains around 2026-10-15

Fixed:
- 2026-09-29 formal V4 permanently UNAVAILABLE
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days / S03_M2 >=100 official observations / clean evidence contract
- historical reconstruction gives no prospective gate credit
- `purchase_action=false`
- never enumerate Railway plaintext Variables
- Railway Agent only when normal MCP cannot answer

Working style: **one task at a time; no long intermediate progress; concise result only; replace stale handoff text instead of appending.**

`LATEST_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_BEFORE_DELETE / HOBBY_PREP / PURCHASE_FALSE`
