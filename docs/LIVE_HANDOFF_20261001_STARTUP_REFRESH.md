# Live Handoff — 2026-10-01 10:57 JST (compact)

Status: **CURRENT COMPACT HANDOFF**  
Repository: `kenshoushouri-cloud/boat-ai-v2`

Re-fetch live state before every action. Snapshot SHA/run/count values are context only.

## 1. Purpose / fixed contract

Goal: build a reproducible positive-expectation boat-race selection system using only information available before each race deadline, without result leakage, hindsight reconstruction, or outcome-guided tuning; move to stable real operation only after evidence gates are met. Monthly +50,000 JPY is a later economic objective, never a reason to loosen selectors or gates.

Fixed:
- GitHub `main` = code Source of Truth; Railway PostgreSQL Production = data Source of Truth
- 2026-09-29 formal V4 = permanently **UNAVAILABLE**
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days + S03_M2 >=100 official observations + clean evidence contract
- historical reconstruction gives **zero** prospective gate credit
- `purchase_action=false`
- Production model/selector/stake/LINE/purchase and Railway Production mutations require explicit approval
- never enumerate Railway plaintext Variables / never call `list_variables`
- prefer normal Railway MCP; Railway Agent only when normal tools cannot answer

## 2. Timeline / formal status

Daily prospective path:
`08:15 cutoff -> 08:16 nominal GitHub -> 08:20 Railway fallback -> availability hard-stop -> pre-deadline freeze -> 23:30 settlement`

Milestones:
- **2026-10-03 billing boundary:** Pro -> Hobby target only after restore/parity/resource checks
- **around 2026-10-15:** V5 core freeze / operational-readiness review target; not automatic go-live

Last settled gate baseline:
- V4 = **8/20** through 2026-09-28
- S03_M2 = **63/100**
- 2026-10-01 fallback freeze run `36790563118` = **SUCCESS**, prospective evidence eligible; do not count until nightly settlement + terminal canonical evidence

## 3. Current work

Snapshot main: `60379047affb581acb4f009d05f08b70aa2b7f01`.

Historical recovery:
- writer `36703692641`: **2026-01 in_progress**; 2026-02..09 queued
- no duplicate normal beforeinfo trigger while this lane is occupied
- after acquisition: `recent_form -> matched-readiness -> matched-contract backtest -> V5 review`

Pro -> Hobby preparation:
- current plan **PRO**; Hobby volume limit **5 GB**
- Production DB = `postgres-recovery`
- volume configured **20 GB**; physical used about **4.95 GB**
- logical DB about **4,221 MB**
- 60-day hot-retention planning estimate: archive candidate about **2,693 MB**; estimate only, not physical-shrink proof
- Railway backup `pre-hobby-migration-20261001` is secured
- encrypted logical archive artifact `boat-ai-pre-hobby-20261001` is secured
- plain dump SHA-256: `2f00b0b14f239fd1069d0dc4e95570201b1572657311ab53ef3f83411fdf733c`
- `pg_restore --list` validation passed; Production rows/schema unchanged

**Next single task: isolated restore drill of the encrypted logical archive.**

Safe order:
`restore drill -> restored parity -> hot-retention finalization -> Hobby-compatible DB/volume -> read-only parity -> explicit cutover approval -> stable cutover -> old-data/volume cleanup -> Pro->Hobby downgrade`

Never delete Production historical data first. PR #534 is Draft/stale against current main; do not merge blindly.

## 4. Working style / handoff hygiene

- one task at a time to avoid timeouts
- no long intermediate progress; concise result only
- replace stale text instead of appending override blocks
- current reading order: `HANDOFF_LATEST.md -> this file -> NEXT_CHAT_START_HERE.md`
- old `LIVE_HANDOFF_*`, `PROJECT_HANDOFF.md`, `CURRENT_STATE.md`, and dated purpose/timeline docs are history unless a specific past decision is needed

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_BEFORE_DELETE / HOBBY_PREP / 929_UNAVAILABLE / V5_GATES_FIXED / PURCHASE_FALSE`
