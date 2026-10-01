# Live Handoff — 2026-10-01 10:49 JST (compact)

Status: **CURRENT COMPACT HANDOFF**  
Repository: `kenshoushouri-cloud/boat-ai-v2`

Re-fetch live GitHub/Railway state before every action. Snapshot values below are context only.

## 1. Purpose / fixed contract

Goal: build a reproducible positive-expectation boat-race selection system using only information available before each race deadline, without result leakage, hindsight reconstruction, or outcome-guided tuning; move to stable real operation only after evidence gates are met. Monthly +50,000 JPY is a later economic objective, not a reason to loosen selectors or gates.

Fixed:
- GitHub `main` = code Source of Truth
- Railway PostgreSQL Production = data Source of Truth
- 2026-09-29 formal V4 = permanently **UNAVAILABLE**
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days + S03_M2 >=100 official observations + clean evidence contract
- historical reconstruction gives **zero** prospective gate credit
- `purchase_action=false`
- Production model/selector/stake/LINE/purchase and Railway Production mutations require explicit approval
- never enumerate Railway plaintext Variables / never call `list_variables`
- prefer normal Railway MCP; use Railway Agent only when normal tools cannot answer

## 2. Timeline

Daily prospective path:
`08:15 cutoff -> 08:16 nominal GitHub -> 08:20 Railway fallback -> availability hard-stop -> pre-deadline freeze -> 23:30 settlement`

Milestones:
- **2026-10-03 billing boundary:** target Pro -> Hobby only after restore/parity/resource checks
- **around 2026-10-15:** V5 core freeze / operational-readiness review target; not automatic go-live

Last settled gate baseline:
- V4 = **8/20** through 2026-09-28
- S03_M2 = **63/100**
- 2026-10-01 fallback freeze run `36790563118` = **SUCCESS**, prospective evidence eligible; do not count it until nightly settlement + terminal canonical evidence

## 3. Current work

Historical recovery:
- writer run `36703692641`: **2026-01 in_progress**; 2026-02..09 queued
- no duplicate normal beforeinfo trigger while this lane is occupied
- after acquisition: `recent_form -> matched-readiness -> matched-contract backtest -> V5 review`

Railway Pro -> Hobby preparation:
- current plan **PRO**; Hobby volume limit **5 GB**
- Production DB = `postgres-recovery`
- configured volume **20 GB**; physical used ≈ **4.95 GB**
- logical DB ≈ **4,221 MB**
- 60-day hot-retention planning estimate: archive candidate ≈ **2,693 MB** across audited tables; planning estimate only
- Railway backup `pre-hobby-migration-20261001` secured
- encrypted logical archive artifact `boat-ai-pre-hobby-20261001` secured
- plain dump SHA-256: `2f00b0b14f239fd1069d0dc4e95570201b1572657311ab53ef3f83411fdf733c`
- `pg_restore --list` validation passed; Production rows/schema unchanged

**Next single task: isolated restore drill of the encrypted logical archive.**

Safe migration order:
`restore drill -> restored parity -> hot-retention finalization -> Hobby-compatible DB/volume -> read-only parity -> explicit cutover approval -> stable cutover -> old-data/volume cleanup -> Pro->Hobby downgrade`

Never delete Production historical data first. PR #534 is Draft/stale against current main; do not merge blindly.

## 4. Working style / context control

- one task at a time to avoid timeouts
- no long intermediate progress; report concise result only
- replace stale handoff text instead of appending override blocks
- old `LIVE_HANDOFF_*`, `PROJECT_HANDOFF.md`, `CURRENT_STATE.md`, and dated purpose/timeline docs are history unless a specific past decision is needed

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_BEFORE_DELETE / HOBBY_PREP / 929_UNAVAILABLE / V5_GATES_FIXED / PURCHASE_FALSE`
