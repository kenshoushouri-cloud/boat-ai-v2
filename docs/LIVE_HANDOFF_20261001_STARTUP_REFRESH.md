# Live Handoff — 2026-10-01 10:13 JST (compact)

Status: **CURRENT COMPACT HANDOFF**  
Repository: `kenshoushouri-cloud/boat-ai-v2`

Re-fetch GitHub/Railway live state before every action. Old SHA/run/count values are snapshots only.

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
- never enumerate Railway plaintext Variables / never call `list_variables`
- Railway Agent is exceptional only; prefer normal MCP reads

## 2. Timeline / prospective checkpoint

Daily path:
`08:15 cutoff -> 08:16 nominal GitHub -> 08:20 Railway fallback -> runtime availability hard-stop -> pre-deadline freeze -> 23:30 settlement`

Milestones:
- **2026-10-03 billing boundary:** Pro -> Hobby only after restore/parity/resource checks
- **around 2026-10-15:** V5 core freeze / operational-readiness review target; not automatic go-live

Prospective baseline:
- V4 = **8/20** settled through 2026-09-28
- S03_M2 = **63/100**
- 2026-09-29 permanently unavailable
- 2026-10-01 fallback freeze run `36790563118` = **SUCCESS**
  - pre-freeze raw capture PASS
  - prospective evidence eligible=true
  - availability guard `PASS_ACTIVE_CORE`
  - immutable artifact + F-count companion created
  - `purchase_action=false`
- 10/1 is not added to V4 until nightly settlement + terminal canonical evidence

## 3. Historical recovery

Existing beforeinfo writer:
- run `36703692641`
- 2025-12 = **in_progress**
- 2026-01..09 = queued
- earlier 2025-08..11 = cancelled
- **do not add another normal beforeinfo trigger while this lane is occupied**

Latest matched-readiness snapshot:
- races = 70,026
- complete_beforeinfo = 14,705
- core_plus_beforeinfo = 7,936 / 11.33%
- opponent_replay = 56,599
- reconstructed full core = 47,431 / 67.73%
- recent_form6 = 0
- historical/read-only only; no prospective gate credit

After beforeinfo recovery: `recent_form -> matched-readiness -> matched-contract backtest -> V5 review`.

## 4. Railway Pro -> Hobby preparation

Billing / limits:
- current plan = **PRO**
- billing boundary = **10/03**
- Pro -> Hobby downgrade takes effect at the next billing cycle
- Hobby volume size limit = **5 GB**

Production DB:
- service = `postgres-recovery`
- configured volume = **20 GB**
- physical disk used ≈ **4.958 GB**
- latest logical DB size = **4,221 MB**
- largest: `v2_odds_trifecta` ≈ 1,831 MB; `v2_realtime_odds_snapshots` ≈ 721 MB

Read-only retention planning estimate:
- keep 30d hot -> archive candidate ≈ **3,261 MB**
- keep 60d hot -> archive candidate ≈ **2,693 MB**
- keep 90d hot -> archive candidate ≈ **2,343 MB**
These are row-proportional estimates, not guaranteed physical disk shrinkage.

Recovery evidence already secured:
- Railway snapshot `pre-hobby-migration-20261001` exists
- encrypted logical archive artifact `boat-ai-pre-hobby-20261001` exists
- plaintext dump bytes = 301,856,594
- SHA-256 = `2f00b0b14f239fd1069d0dc4e95570201b1572657311ab53ef3f83411fdf733c`
- `pg_restore --list` validation passed; 272 entries
- plaintext dump was never uploaded to the public repo
- Production rows/schema were unchanged

PR #534:
- Draft `Ops: add read-only Hobby retention sizing audit`
- open, stale/non-mergeable against current main
- do not merge blindly; rebase/revalidate only if still needed

## 5. Immediate next work

Principle: **archive first -> prove restore -> prove parity -> cut over -> only then clean up/downgrade.**

**Next single task: isolated restore drill of the encrypted pre-Hobby logical archive.**

Then, one task at a time:
1. verify restored schema/table/row counts
2. finish hot-retention dependency audit; 60d is only a working candidate
3. build a smaller Hobby-compatible DB/volume
4. run read-only parity checks
5. only with explicit exact-target approval: Production cutover
6. after stable cutover: old-data/volume cleanup and plan downgrade

Do not run Production DELETE/schema/VACUUM, volume replacement, Cron/Variables changes, cutover, or plan change before restore/parity.

## 6. Working style / context control

User request:
- **one task at a time** to avoid timeouts
- no long intermediate progress in chat
- report only concise completion/result
- keep this handoff compact; replace stale text instead of appending

Deep-history docs are reference only and should not be loaded by default.

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_BEFORE_DELETE / HOBBY_PREP / 929_UNAVAILABLE / V5_GATES_FIXED / PURCHASE_FALSE`
