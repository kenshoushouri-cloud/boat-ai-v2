# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_STARTUP_REFRESH.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only the live state required for the next single task.

Current focus:
- preserve daily prospective evidence
- historical writer `36703692641` remains occupied; do not duplicate-trigger
- prepare Pro -> Hobby for the 2026-10-03 billing boundary
- Railway backup + current restore/parity-verified encrypted archive are secured
- restore/parity run `36812386066` = **SUCCESS**
- current recovery artifact id `11139857666`; artifact = `boat-ai-pre-hobby-restorable-20261001-v3-parity-36812386066`
- exact parity passed for all 39 public table row counts plus schema metadata
- hot-retention finalization run `36813600010` = **SUCCESS**
- retention mode = **FULL_HISTORY_PINNED**
- fresh full restore baseline = **3,615,987,391 bytes**; projected +14d = **4,034,454,006 bytes**
- 5 GB planning headroom after projection = **965,545,994 bytes**
- do not use the old 60d filtered candidate as a cutover reference
- **next single task = Hobby-compatible 5 GB full-history DB/volume candidate**
- no Production delete, cutover, volume cleanup, or plan downgrade before candidate parity is accepted
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

Working style: **one task at a time; concise result only; replace stale text instead of appending.**

`LATEST_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_VERIFIED / EXACT_PARITY_VERIFIED / FULL_HISTORY_PINNED / HOBBY_PREP / PURCHASE_FALSE`
