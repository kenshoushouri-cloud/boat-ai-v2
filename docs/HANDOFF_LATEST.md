# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_STARTUP_REFRESH.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only the live state required for the next single task.

Current focus:
- preserve daily prospective evidence
- let historical writer `36703692641` continue; no duplicate trigger
- prepare Pro -> Hobby for the 2026-10-03 billing boundary
- Railway backup + current restore/parity-verified encrypted archive are secured
- current restore/parity run `36812386066` = **SUCCESS**
- current artifact id `11139857666`; artifact = `boat-ai-pre-hobby-restorable-20261001-v3-parity-36812386066`
- dump/restored SHA-256 = `87dea392d2667509c5040d3fd9bff85ffbbd2dc0d5dec974cba9f75a29e062ab`
- exact parity passed for all 39 public table row counts plus table metadata / columns / constraints / indexes / sequences / views / triggers / policies / extensions
- source/restored evidence SHA-256 = `658bac46705b3006fdc0ee370e9370bf90a484bc2a8767d8cc29734ae0af603d`
- v2 artifacts are historical; v3 uses a run-scoped escrow key and must be the recovery reference
- **next single task = hot-retention finalization**
- no Production delete, cutover, volume cleanup, or plan downgrade before the Hobby-compatible set and parity are accepted
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

`LATEST_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_VERIFIED / EXACT_PARITY_VERIFIED / HOBBY_PREP / PURCHASE_FALSE`
