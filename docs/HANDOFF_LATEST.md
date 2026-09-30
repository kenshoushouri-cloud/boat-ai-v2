# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_STARTUP_REFRESH.md`

Start every new chat in this order:
1. `docs/HANDOFF_LATEST.md`
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`
4. deep history only when needed

Before any action, re-fetch:
- current GitHub main
- Issue #42 latest relevant comments
- open Draft PR / CI / active Actions
- Railway Production fallback/status
- Production PostgreSQL evidence needed for the task

Source of Truth:
- GitHub `main` = code
- Railway PostgreSQL Production = data

Fixed:
- 2026-09-29 formal V4 = permanently UNAVAILABLE
- V5 gate = V4 >=20 resolved FORMAL_AVAILABLE days / S03_M2 >=100 official observations / clean evidence contract
- historical reconstruction gives no prospective gate credit
- monthly +50,000 JPY is a post-edge scaling target, not a selector target
- `purchase_action=false`
- do not enumerate Railway plaintext variables

Handoff maintenance:
- do not append cumulative `LATEST OVERRIDE` sections
- keep one compact live handoff and this pointer
- use Git history / dated deep-history docs for old detail

`LATEST_COMPACT_HANDOFF / REFETCH_BEFORE_ACTION / ONE_OR_TWO_CHECKS / PURCHASE_FALSE`
