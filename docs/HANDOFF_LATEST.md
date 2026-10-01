# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_STARTUP_REFRESH.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do **not** load old `LIVE_HANDOFF_*`, `PROJECT_HANDOFF.md`, `CURRENT_STATE.md`, or `SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md` by default. They are deep history and should be opened only when a specific past decision is needed.

Before every action, re-fetch only the live state required for that one task.

Source of Truth:
- GitHub `main` = code
- Railway PostgreSQL Production = data

Current focus:
- preserve daily prospective evidence
- continue historical recovery without duplicate writers
- safely prepare Pro -> Hobby around the 10/03 billing boundary
- next migration task = isolated restore drill
- archive -> restore -> parity -> cutover; never delete first
- V5 operational-readiness target remains around 2026-10-15

Fixed:
- 2026-09-29 formal V4 permanently UNAVAILABLE
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days / S03_M2 >=100 official observations / clean evidence contract
- historical reconstruction gives no prospective gate credit
- `purchase_action=false`
- never enumerate Railway plaintext Variables

Working style:
- one task at a time
- concise completion reports only
- consolidate/replace stale handoff text; never append cumulative overrides

`LATEST_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_BEFORE_DELETE / PURCHASE_FALSE`
