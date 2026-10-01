# Live Handoff — 2026-10-01 09:10 JST (compact)

Status: **CURRENT COMPACT HANDOFF**  
Repository: `kenshoushouri-cloud/boat-ai-v2`

This file is the current working handoff. Re-fetch live GitHub/Railway state before every action. Old SHA/run/count values are snapshots, not permanent truth.

## 1. System purpose / fixed contract

Goal: build a reproducible positive-expectation boat-race selection system using only information available before each race deadline, with no result leakage, hindsight reconstruction, or outcome-guided tuning.

Source of Truth:
- GitHub `main` = code
- Railway PostgreSQL Production = data

Fixed:
- 2026-09-29 formal V4 = permanently **UNAVAILABLE**
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days + S03_M2 >=100 official observations + clean evidence contract
- historical reconstruction gives **zero prospective gate credit**
- `purchase_action=false`
- Production model/selector/stake/LINE/purchase and Railway Production mutations require explicit approval
- never enumerate Railway plaintext Variables; do not call `list_variables`
- Railway Agent is exceptional only; prefer normal MCP reads

## 2. Timeline / current checkpoints

Daily prospective path:
`08:15 cutoff -> 08:16 nominal GitHub -> 08:20 Railway fallback -> runtime availability hard-stop -> pre-deadline freeze -> 23:30 settlement`

Milestones:
- **2026-10-03 billing boundary:** Pro -> Hobby preparation/cutover only if restore/parity/resource limits are proven; never delete first just to meet the date
- **around 2026-10-15:** V5 core freeze / operational-readiness review target; not automatic go-live

Prospective baseline:
- V4 = **8/20** settled through 2026-09-28
- S03_M2 = **63/100**
- 2026-09-29 = permanently unavailable
- 2026-10-01 fallback freeze run `36790563118` = **SUCCESS**
  - pre-freeze raw capture PASS
  - prospective evidence eligible=true
  - availability guard `PASS_ACTIVE_CORE`
  - immutable artifact + F-count companion created
  - `purchase_action=false`
- 10/1 does not advance V4 until nightly settlement and terminal canonical evidence

## 3. Historical recovery

Active beforeinfo writer:
- run `36703692641`
- 2025-12 job = **in_progress**
- 2026-01..09 = queued
- earlier 2025-08..11 = cancelled
- do not add another normal beforeinfo trigger while this lane is occupied

Latest matched-readiness snapshot:
- total races/exact6/fcount6/motor6 = 70,026
- opponent_replay = 56,599
- reconstructed full core = 47,431 / 67.73%
- complete_beforeinfo = 14,705
- core_plus_beforeinfo = 7,936 / 11.33%
- recent_form6 = 0
- historical/read-only only; no prospective gate credit

## 4. Railway Pro -> Hobby preparation

Current:
- workspace plan = **PRO**
- user billing boundary = **10/03**
- Hobby volume size limit = **5 GB**
- Production DB = `postgres-recovery`
- current volume used ≈ **4.95 GB**
- configured volume = **20 GB**
- latest logical DB size = **4,221 MB**

Largest relations:
- `v2_odds_trifecta` ≈ 1,831 MB
- `v2_realtime_odds_snapshots` ≈ 721 MB
- `v2_v24_motor2_forward_shadow` ≈ 269 MB
- `v2_result_entries` ≈ 223 MB

Read-only retention planning estimate:
- 30d hot -> archive candidate ≈ **3,261 MB**
- 60d hot -> archive candidate ≈ **2,693 MB**
- 90d hot -> archive candidate ≈ **2,343 MB**
These are row-proportional planning estimates, not guaranteed physical disk shrinkage.

Recovery evidence already secured:
- Railway snapshot `pre-hobby-migration-20261001` exists
- encrypted logical archive artifact `boat-ai-pre-hobby-20261001` exists
- plaintext dump bytes = 301,856,594
- SHA-256 = `2f00b0b14f239fd1069d0dc4e95570201b1572657311ab53ef3f83411fdf733c`
- `pg_restore --list` validation passed; 272 entries
- plaintext dump was not uploaded to the public repo
- archive creation made no Production row/schema change

PR #534:
- Draft: `Ops: add read-only Hobby retention sizing audit`
- current base is stale after later main docs commits; current read-back reports non-mergeable
- rebase/revalidate before any merge; do not merge blindly

## 5. Safe migration sequence / immediate next task

Principle: **archive first -> prove restore -> prove parity -> cut over -> only then clean up/downgrade.**

Next task: **isolated restore drill of the encrypted pre-Hobby logical archive**.

Sequence:
1. re-fetch live main / PR #534 / writer lane / DB size
2. restore the verified archive into an isolated scratch PostgreSQL target
3. verify schema/table/row-count integrity
4. finish hot-retention dependency audit; 60d is only a working candidate
5. build a smaller Hobby-compatible DB/volume from verified data
6. run read-only parity checks
7. only after explicit approval: Production cutover, old-data/volume cleanup, plan downgrade

Do not run Production DELETE/schema/VACUUM, volume replacement, service/Cron/Variables changes, Production cutover, or plan change without exact-target approval.

## 6. Working style

User request:
- **one task at a time** to avoid timeouts
- no long intermediate progress in chat; report only concise completion/result
- keep handoff compact; replace stale text instead of appending

Deep-history documents, including `SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`, are historical reference only and should not be loaded by default.

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_BEFORE_DELETE / HOBBY_PREP / 929_UNAVAILABLE / V5_GATES_FIXED / PURCHASE_FALSE`
