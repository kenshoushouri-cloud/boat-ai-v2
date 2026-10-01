# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_STARTUP_REFRESH.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state required for the next single task.

Current focus:
- preserve daily prospective evidence
- do not duplicate-trigger historical writer `36703692641`
- prepare Pro -> Hobby for the 2026-10-03 billing boundary
- backup + encrypted restore/parity-verified archive secured
- retention policy = **FULL_HISTORY_PINNED**
- current isolated 5 GB candidate = `postgres-hobby-fullhistory-candidate-v3`
- candidate ENOSPC diagnostic found two missing indexes
- `ux_v2_venues_venue_id` repair = **DONE**
- remaining blocker = `ux_v2_odds_trifecta_race_ticket` under 5 GB constraint
- **next single task = candidate-only remaining-index resolution, then exact parity**
- no Production cutover/delete/resize/plan change before parity acceptance
- V5 operational-readiness review target remains around 2026-10-15

Fixed:
- GitHub `main` = code Source of Truth
- Railway PostgreSQL Production = data Source of Truth
- 2026-09-29 formal V4 permanently UNAVAILABLE
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days / S03_M2 >=100 official observations / clean evidence contract
- historical reconstruction gives no prospective gate credit
- `purchase_action=false`
- never enumerate Railway plaintext Variables
- Railway Agent only when normal MCP cannot answer

Timeout discipline:
- one task at a time
- concise result only
- avoid broad GitHub Actions/log/comment fetches; query only specific run/page/resource

`LATEST_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / AVOID_BULK_OUTPUT / FULL_HISTORY_PINNED / 5GB_CANDIDATE / PARITY_BEFORE_CUTOVER / PURCHASE_FALSE`
