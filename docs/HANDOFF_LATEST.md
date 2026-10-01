# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_STARTUP_REFRESH.md`

Read in this order:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`
4. deep history only when a specific past decision is needed

Before any action, re-fetch the live state relevant to that one task.

Source of Truth:
- GitHub `main` = code
- Railway PostgreSQL Production = data

Current focus:
- preserve daily prospective evidence
- continue historical missing-data recovery without duplicate writers
- safely prepare Pro -> Hobby migration for the 10/03 billing boundary
- archive -> restore drill -> parity -> cutover; never delete first
- V5 operational-readiness target remains around 2026-10-15

Fixed:
- 2026-09-29 formal V4 permanently UNAVAILABLE
- V5 gate = V4 >=20 resolved FORMAL_AVAILABLE days / S03_M2 >=100 official observations / clean evidence contract
- historical reconstruction gets no prospective gate credit
- `purchase_action=false`
- do not enumerate Railway plaintext variables

Handoff hygiene:
- no cumulative `LATEST OVERRIDE` blocks
- replace/consolidate stale text instead of appending
- keep exactly one current compact handoff; use Git history for old detail

`LATEST_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / REFETCH_BEFORE_ACTION / PURCHASE_FALSE`
