# Live Handoff — 2026-10-01 post-retention-finalization (compact)

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
- **2026-10-03 billing boundary:** Pro -> Hobby target; finish candidate/parity/resource checks first
- **around 2026-10-15:** V5 core freeze / operational-readiness review target; not automatic go-live

Last settled baseline snapshot:
- V4 = **8/20** through 2026-09-28
- S03_M2 = **63/100**
- 2026-10-01 fallback freeze run `36790563118` = **SUCCESS**, prospective evidence eligible
- do not add 2026-10-01 to resolved V4 before nightly settlement + terminal canonical evidence
- delayed scheduled run `36804250424` later failed; it must not replace the earlier valid fallback artifact

## 3. Current work

Historical recovery:
- writer `36703692641`: live API snapshot = **queued**; do not duplicate-trigger
- after acquisition: `recent_form -> matched-readiness -> matched-contract backtest -> V5 review`

Pro -> Hobby preparation:
- current plan = **PRO**; Hobby volume limit = **5 GB**
- Production DB = `postgres-recovery`
- Railway backup `pre-hobby-migration-20261001` secured
- restore-key escrow service = `archive-restore-key-20261001`
- restore/parity run `36812386066` = **SUCCESS**
- current recovery artifact = `boat-ai-pre-hobby-restorable-20261001-v3-parity-36812386066`, artifact id `11139857666`
- exact parity passed for **39 public tables / 771 columns / 289 constraints / 98 indexes / 24 sequences / 0 views / 0 triggers / 0 policies / 1 extension**
- dump/restored SHA-256 = `87dea392d2667509c5040d3fd9bff85ffbbd2dc0d5dec974cba9f75a29e062ab`
- source/restored evidence SHA-256 = `658bac46705b3006fdc0ee370e9370bf90a484bc2a8767d8cc29734ae0af603d`
- `SOURCE_WRITE=0`; Production rows/schema unchanged; plaintext dump/private key not uploaded

Retention finalization:
- run `36813600010` = **SUCCESS**
- evidence artifact `hobby-retention-finalization-36813600010`, id `11139948972`
- evidence SHA-256 = `671c9044250cd791061fe4c516a8263591a2dad83302a6c1f74a64b2c4f8273d`
- policy = **FULL_HISTORY_PINNED**
- source DB snapshot = **4,437,243,583 bytes**
- fresh exact-parity full restore = **3,615,987,391 bytes**
- estimated next-14-day growth = **418,466,615 bytes** (planning estimate)
- projected fresh full restore +14d = **4,034,454,006 bytes**
- planning headroom vs 5,000,000,000 bytes = **965,545,994 bytes**
- deleting the five proposed hot-only tables to 60d/90d now would remove about **2,171/1,979 MiB**
- labeled historical rows affected = **843,072 at 60d / 776,676 at 90d**
- historical matched-contract path needs historical weather/exhibition back to 2025-07-01, so do not delete these rows yet
- policy source: `ops/hobby-migration/RETENTION_POLICY_20261001.md`
- old 60d filtered `postgres-hobby-candidate` is **not** a cutover reference

**Next single task: create/prepare a Hobby-compatible 5 GB full-history DB/volume candidate, restore the current recovery reference into it, then verify read-only parity before any cutover.**

Safe order:
`restore DONE -> exact parity DONE -> retention finalization DONE -> 5GB full-history candidate -> read-only parity -> explicit cutover approval -> stable cutover -> old-data/volume cleanup -> Pro->Hobby downgrade`

Do not delete Production historical data first. PR #534 remains Draft/stale against current main; do not merge blindly.

## 4. Handoff / operating discipline

- one task at a time to avoid timeouts
- no long intermediate progress; concise result only
- replace stale text instead of appending override blocks
- reading order: `HANDOFF_LATEST.md -> this file -> NEXT_CHAT_START_HERE.md`
- old `LIVE_HANDOFF_*`, `PROJECT_HANDOFF.md`, `CURRENT_STATE.md`, and dated purpose/timeline docs are history unless a specific past decision is needed

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_VERIFIED / EXACT_PARITY_VERIFIED / FULL_HISTORY_PINNED / HOBBY_PREP / 929_UNAVAILABLE / V5_GATES_FIXED / PURCHASE_FALSE`
