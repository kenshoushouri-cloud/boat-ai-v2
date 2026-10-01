# Live Handoff — 2026-10-01 10:18 JST (compact)

Status: **CURRENT COMPACT HANDOFF**  
Repository: `kenshoushouri-cloud/boat-ai-v2`

Re-fetch live GitHub/Railway state before every action. Values below are snapshots, not permanent truth.

## 1. System purpose / fixed contract

Goal: build a reproducible positive-expectation boat-race selection system using only information available before each race deadline, with no result leakage, hindsight reconstruction, or outcome-guided tuning.

Source of Truth:
- GitHub `main` = code
- Railway PostgreSQL Production = data

Fixed:
- 2026-09-29 formal V4 = permanently **UNAVAILABLE**
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days + S03_M2 >=100 official observations + clean evidence contract
- historical reconstruction gives **zero** prospective gate credit
- `purchase_action=false`
- Production model/selector/stake/LINE/purchase and Railway Production mutations require explicit approval
- never enumerate Railway plaintext Variables / never call `list_variables`
- prefer normal Railway MCP reads; Railway Agent only when required

## 2. Timeline / gates

Daily prospective path:
`08:15 cutoff -> 08:16 nominal GitHub -> 08:20 Railway fallback -> availability hard-stop -> pre-deadline freeze -> 23:30 settlement`

Milestones:
- **2026-10-03 billing boundary:** Pro -> Hobby only after restore/parity/resource checks
- **around 2026-10-15:** V5 core freeze / operational-readiness review target; not automatic go-live

Prospective baseline:
- V4 = **8/20** settled through 2026-09-28
- S03_M2 = **63/100**
- 2026-09-29 permanently unavailable
- 2026-10-01 fallback freeze run `36790563118` = **SUCCESS**
- 10/1 is not added to V4 until nightly settlement + terminal canonical evidence

## 3. Current work

### Historical recovery
- existing writer run `36703692641`
- 2025-12 = **in_progress**; 2026-01..09 = queued
- do **not** add another normal beforeinfo trigger while this lane is occupied
- latest matched-readiness snapshot: complete_beforeinfo **14,705**, core_plus_beforeinfo **7,936 / 11.33%**, opponent_replay **56,599**, recent_form6 **0**
- next research sequence: `recent_form -> matched-readiness -> matched-contract backtest -> V5 review`

### Railway Pro -> Hobby
- plan = **PRO**; billing boundary = **10/03**; Hobby volume limit = **5 GB**
- Production DB = `postgres-recovery`
- configured volume = **20 GB**; physical disk used ≈ **4.96 GB**
- logical DB size ≈ **4,221 MB**
- largest relations: `v2_odds_trifecta` ≈ 1,831 MB; `v2_realtime_odds_snapshots` ≈ 721 MB
- read-only archive estimates: keep 30d -> **3,261 MB**, 60d -> **2,693 MB**, 90d -> **2,343 MB** archive candidates; estimates are not guaranteed physical shrinkage

Recovery evidence secured:
- Railway backup/snapshot `pre-hobby-migration-20261001`
- encrypted logical archive artifact `boat-ai-pre-hobby-20261001`
- plain dump SHA-256 `2f00b0b14f239fd1069d0dc4e95570201b1572657311ab53ef3f83411fdf733c`
- `pg_restore --list` validation passed; Production rows/schema unchanged

**Next single task: isolated restore drill of the encrypted logical archive.**

After that, one task at a time:
1. verify restored schema/table/row counts
2. finalize hot-retention scope; 60d is only a working candidate
3. build a Hobby-compatible <=5 GB DB/volume
4. run read-only parity checks
5. only with explicit exact-target approval: Production cutover
6. after stable cutover: old-data/volume cleanup and Pro -> Hobby downgrade

Never delete Production historical data first. Archive -> restore -> parity -> cutover -> cleanup.

PR #534 is Draft/stale against current main; do not merge blindly.

## 4. Working style / context control

- **one task at a time** to avoid timeouts
- no long intermediate progress in chat; report concise completion/results
- replace stale handoff text instead of appending cumulative override blocks
- old `LIVE_HANDOFF_*`, `PROJECT_HANDOFF.md`, `CURRENT_STATE.md`, and `SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md` are deep history unless a specific past decision is needed

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_BEFORE_DELETE / HOBBY_PREP / 929_UNAVAILABLE / V5_GATES_FIXED / PURCHASE_FALSE`
