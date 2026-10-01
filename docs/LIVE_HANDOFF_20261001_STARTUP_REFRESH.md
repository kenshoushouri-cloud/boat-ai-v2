# Live Handoff — 2026-10-01 09:10 JST (compact)

Status: **CURRENT COMPACT HANDOFF**

Repository: `kenshoushouri-cloud/boat-ai-v2`

This is the only mutable handoff. Re-fetch live state before acting; SHA/run/deploy/count values below are snapshots.

## 1. System purpose / fixed contract

Goal: build a reproducible positive-expectation boat-race selection system using only information available before each race deadline, without result leakage, hindsight reconstruction, or outcome-guided tuning.

Source of Truth:
- GitHub `main` = code
- Railway PostgreSQL Production = data

Fixed:
- 2026-09-29 formal V4 = permanently **UNAVAILABLE**
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days + S03_M2 >=100 officially evaluated observations + clean evidence contract
- historical reconstruction gives **zero prospective gate credit**
- monthly net-profit +50,000 JPY is a later scaling objective, not a selector/threshold target
- `purchase_action=false`
- Production model/selector/stake/LINE/purchase and Railway Production mutations require explicit approval
- never enumerate Railway plaintext variables; do not call `list_variables`

## 2. Timeline / priority

Daily prospective priority:
`08:15 cutoff -> 08:16 nominal GitHub -> 08:20 Railway fallback -> runtime-derived availability hard-stop -> pre-deadline freeze -> 23:30 settlement`

Milestones:
- **2026-10-03 billing boundary:** prepare a safe Pro -> Hobby downgrade only if archive/restore/parity and Hobby resource limits are proven; do not force the date by deleting first
- **2026-10-15 around:** V5 core freeze / operational-readiness review target; not an automatic go-live date

Last verified prospective baseline:
- V4 = **8/20** through 2026-09-28
- S03_M2 = **63/100**
- 2026-09-29 = permanently unavailable
- 2026-10-01 fallback formal freeze run `36790563118` = **SUCCESS**
  - pre-freeze availability capture PASS
  - prospective evidence eligible=true
  - availability guard `PASS_ACTIVE_CORE`
  - immutable freeze uploaded
  - F-count companion PASS
  - `purchase_action=false`
- 10/1 is not a resolved V4 day until nightly settlement/terminal canonical evidence exists

## 3. Current GitHub / historical work

Current `main`:
- `d82ac1af1f1ef427a0dcb37a83d520e9799f9b92`
- latest: `Fix pre-Hobby logical archive job indentation`

Relevant current Draft:
- PR #534 `Ops: add read-only Hobby retention sizing audit`
- head `887007ea45f4d565403b1626f337ede4d69d4682`
- mergeable=true; latest exact-head relevant CI is green
- do not merge blindly; re-fetch current main/head first

Historical beforeinfo:
- run `36703692641`: job-level `2025-12-01..2025-12-31` still **in_progress**; 2026-01..09 jobs queued; earlier 2025-08..11 jobs cancelled
- run `36783707390`: legacy monthly replacement remains pending/no jobs
- do not add another normal beforeinfo trigger while writer lane is occupied

Latest matched-readiness evidence:
- races/exact6/fcount6/motor6 = 70,026
- opponent_replay = 56,599
- reconstructed full core = 47,431 / 67.73%
- complete_beforeinfo = 14,705
- core_plus_beforeinfo = 7,936 / 11.33%
- recent_form6 = 0
- historical/read-only only; no prospective gate credit

## 4. Railway / Hobby migration state

Railway:
- workspace plan = **PRO**
- billing boundary shown by user = **10/03**
- Pro -> Hobby downgrade takes effect at the next billing cycle
- Hobby volume size limit = **5 GB**
- routine checks must use normal Railway MCP first; Railway Agent only when ordinary tools cannot answer

Production DB:
- service = `postgres-recovery`
- current volume used ≈ **4.95 GB**
- configured volume = **20 GB**
- latest logical DB size = **4,221 MB**

Largest relations:
- `v2_odds_trifecta` ≈ 1,831 MB
- `v2_realtime_odds_snapshots` ≈ 721 MB
- `v2_v24_motor2_forward_shadow` ≈ 269 MB
- `v2_result_entries` ≈ 223 MB

Read-only retention estimate across listed large tables:
- keep 30d hot -> archive candidate ≈ **3,261 MB**
- keep 60d hot -> archive candidate ≈ **2,693 MB**
- keep 90d hot -> archive candidate ≈ **2,343 MB**

These are row-proportional planning estimates, not promises of physical disk shrinkage.

Recovery evidence already secured:
- Railway snapshot `pre-hobby-migration-20261001` exists
- encrypted logical archive artifact `boat-ai-pre-hobby-20261001` exists
- plaintext dump bytes = 301,856,594
- SHA-256 = `2f00b0b14f239fd1069d0dc4e95570201b1572657311ab53ef3f83411fdf733c`
- `pg_restore --list` validation passed; 272 entries
- plaintext dump was not uploaded to the public repository
- no Production rows/schema were changed by archive creation

## 5. Safe migration sequence

Do **not** delete old rows first.

Next sequence:
1. Re-fetch main / PR #534 / writer lane / DB size.
2. Verify the encrypted logical archive artifact and recovery metadata.
3. Perform an **isolated restore drill** and verify schema/table/row-count integrity.
4. Finish dependency audit for hot retention; 60 days is a working candidate, not yet a delete boundary.
5. Build/restore a smaller Hobby-compatible DB/volume from the verified archive/hot dataset.
6. Run read-only parity checks against Production.
7. Only after explicit approval: Production cutover, old-data/old-volume cleanup, and plan downgrade.
8. Keep external/restorable historical archive for future backtests.

Principle: **archive first -> prove restore -> prove parity -> cut over -> only then clean up/downgrade.**

## 6. Safety / working style

User request:
- work **one task at a time** to avoid timeouts
- do not flood chat with intermediate progress; report concise completion/result

Approval boundary:
- read-only audit, research/backtest, evidence collection, Draft PR, CI, compact docs may continue
- destructive/high-impact actions require the exact target to be stated and individually approved:
  - Production DB DELETE/schema/VACUUM
  - volume detach/delete/replace
  - Production service/Cron/Variables/config changes
  - Production model/selector/stake/LINE/purchase changes
  - actual Production cutover / plan change
- never use historical reconstruction to repair a prospective unavailable day

## 7. Immediate next task

**Restore drill preparation / execution for the encrypted pre-Hobby logical archive, isolated from Production.**

Before starting, re-fetch current main and ensure no newer completed restore drill already exists.

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / RESTORE_BEFORE_DELETE / HOBBY_PREP / 929_UNAVAILABLE / V5_GATES_FIXED / PURCHASE_FALSE`
