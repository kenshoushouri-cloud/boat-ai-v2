# Live Handoff — 2026-10-01 post-parity (compact)

Status: **CURRENT COMPACT HANDOFF**  
Repository: `kenshoushouri-cloud/boat-ai-v2`

Re-fetch live state before every action. SHA/run/count values below are snapshots only.

## 1. System purpose / fixed contract

Goal: build a reproducible positive-expectation boat-race selection system using only information available before each race deadline. No result leakage, hindsight reconstruction, or outcome-guided tuning. Stable real operation starts only after fixed evidence gates are met. Monthly +50,000 JPY is a later economic objective, never a reason to loosen gates.

Fixed:
- GitHub `main` = code Source of Truth; Railway PostgreSQL Production = data Source of Truth
- 2026-09-29 formal V4 = permanently **UNAVAILABLE**
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days + S03_M2 >=100 official observations + clean evidence contract
- historical reconstruction gives **zero** prospective gate credit
- `purchase_action=false`
- Production model/selector/stake/LINE/purchase and Railway Production mutations require explicit approval
- never enumerate Railway plaintext Variables / never call `list_variables`
- prefer normal Railway MCP; use Railway Agent only when normal tools cannot answer

## 2. Time schedule / formal status

Daily:
`08:15 cutoff -> 08:16 nominal GitHub -> 08:20 Railway fallback -> pre-deadline formal freeze -> 23:30 settlement`

Milestones:
- **2026-10-03 billing boundary:** Pro -> Hobby target; finish retention/resource/parity checks first
- **around 2026-10-15:** V5 core freeze / operational-readiness review target; not automatic go-live

Last settled baseline snapshot:
- V4 = **8/20** through 2026-09-28
- S03_M2 = **63/100**
- 2026-10-01 fallback freeze run `36790563118` = **SUCCESS**, prospective evidence eligible
- do not add 2026-10-01 to resolved V4 before nightly settlement + terminal canonical evidence
- delayed scheduled run `36804250424` later failed; it must not replace the earlier valid fallback artifact

## 3. Current work

Historical recovery:
- writer `36703692641`: snapshot = **2026-01 in_progress**; later months queued
- no duplicate normal beforeinfo trigger while this lane is occupied
- after acquisition: `recent_form -> matched-readiness -> matched-contract backtest -> V5 review`

Pro -> Hobby preparation:
- current plan = **PRO**; Hobby volume limit = **5 GB**
- Production DB = `postgres-recovery`
- Production volume = configured **20 GB**; previous physical-used snapshot about **4.95 GB**
- Railway backup `pre-hobby-migration-20261001` secured
- restore-key escrow service = `archive-restore-key-20261001`
- current restore-verified run = `36811231115` **SUCCESS**
- current encrypted artifact = `boat-ai-pre-hobby-restorable-20261001-v2`, artifact id `11138759678`
- current dump SHA-256 = `493374319f2475d74da7ae50edb4709c5bb882ad14ce9bc5eab68d8843e80356`
- prior same-name artifact id `11138584090` is historical only; a later restore drill rotated the escrow key, so do not use it as the current recovery artifact
- restored parity expansion run `36812219830` = **SUCCESS**
- restored public tables = **39**
- canonical schema evidence lines = **1221**
- source/restored schema SHA-256 = `aa2c7ad6291e65e97cadb86dbd9daeed1761e61c5b7f3b1fefb7e5fed97ab93d`
- exact schema parity passed for tables / columns / constraints / indexes / sequences / triggers / public enum-domain types
- 10 additional critical tables passed `live source rows >= restored archive rows`; positive deltas were only post-archive live writes
- `SOURCE_WRITE=0`; Production rows/schema unchanged; plaintext dump/private key not uploaded

**Next single task: hot-retention finalization for the Hobby-compatible data set.**

Safe order:
`restore drill DONE -> restored parity DONE -> hot-retention finalization -> Hobby-compatible DB/volume -> read-only parity -> explicit cutover approval -> stable cutover -> old-data/volume cleanup -> Pro->Hobby downgrade`

Do not delete Production historical data first. PR #534 remains Draft/stale against current main; do not merge blindly.

## 4. Handoff / operating discipline

- one task at a time to avoid timeouts
- no long intermediate progress; concise result only
- replace stale text instead of appending override blocks
- reading order: `HANDOFF_LATEST.md -> this file -> NEXT_CHAT_START_HERE.md`
- old `LIVE_HANDOFF_*`, `PROJECT_HANDOFF.md`, `CURRENT_STATE.md`, and dated purpose/timeline docs are history unless a specific past decision is needed

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_VERIFIED / PARITY_VERIFIED / HOBBY_PREP / 929_UNAVAILABLE / V5_GATES_FIXED / PURCHASE_FALSE`
