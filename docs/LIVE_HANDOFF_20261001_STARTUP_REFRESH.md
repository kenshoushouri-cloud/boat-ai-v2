# Live Handoff — 2026-10-01 startup refresh (compact)

Status: **CURRENT COMPACT HANDOFF**

Repository: `kenshoushouri-cloud/boat-ai-v2`

This file replaces long cumulative handoff chains. Re-fetch live state before acting; SHA/run/deploy/coverage values below are snapshots, not permanent facts.

## 1. Non-negotiable contract

- GitHub `main` = code Source of Truth.
- Railway PostgreSQL Production = data Source of Truth.
- Use only information available before each race deadline; no target-race outcome leakage or hindsight reconstruction.
- 2026-09-29 formal V4 is permanently **UNAVAILABLE**. Never reconstruct or count it.
- V5 core gate stays:
  - V4 >= 20 resolved `FORMAL_AVAILABLE` days
  - S03_M2 >= 100 officially evaluated observations
  - evidence contract clean
- Historical reconstruction never receives prospective gate credit.
- Monthly net-profit +50,000 JPY is a later scaling objective; never loosen selector/thresholds to force volume or revenue.
- `purchase_action=false`.
- Production V4 model/selector/stake/LINE/purchase and Railway Production config require explicit approval before change.
- Do not enumerate Railway plaintext variables; do not call `list_variables`.

## 2. Daily priority — JST

`08:15 cutoff -> 08:16 nominal GitHub -> 08:20 Railway fallback -> 08:32 availability hard-stop -> before-deadline formal freeze -> 23:30 nightly settlement`

At startup on 2026-10-01, preserve the morning prospective path first. Do not introduce Production behavior changes before the morning cycle.

## 3. Current GitHub read-back

Current `main`:
- `b26efcb87230f5925331c700b0b73c77b9fc5197`
- merge PR #531, docs-only handoff refresh

Historical runs:
- `36667832406` = **completed / failure**
  - Phase 1 B-file = SUCCESS
  - Phase 2 archived-racelist residual = SUCCESS
  - Phase 3 prior-only Opponent replay = FAILURE
  - do not restart the full campaign; recover only verified residuals later
- `36667954064` = **in_progress**
  - segment 1 cancelled
  - segment 2 cancelled
  - segment 3 `2026-09-14..2026-09-29` is actively filling beforeinfo
  - do not duplicate-trigger
- `36703692641` = queued at run level on latest Actions read-back; re-read jobs before any cleanup action

Old branch:
- `ops/command-aware-historical-concurrency-20260930-v2`
- exists, but compare against current main = **ahead 0 / behind 44**
- no unique changes remain; treat as superseded/inactive

Beforeinfo routing:
- #526 = open Draft, current-main based, mergeable=true, head `a779f5280a95e65f759ca957db30a4d3a97206fb`
- #526 relevant CI = 6/6 SUCCESS
- #528 and #529 = closed without merge
- #526 merge changes operational workflow routing, so **explicit approval is required before merge**

9/30 combined checkpoint:
- no terminal `Research Forward Combined Checkpoint Manual` run found in the latest 100 Actions runs
- therefore do **not** advance V4/S03 gates from the last verified baseline yet

## 4. Railway Production read-back

Project:
- `boat-v2-postgres`
- project id `268a5b17-0712-440a-884d-27f7fa887a2d`
- Production env `5ffb02f6-5ec8-4268-9bda-8e30431ff625`

Fallback:
- service `candidate-discovery-v4-fallback-dispatcher`
- id `84010f63-8e5a-4ad3-8718-bdad3dd9c436`
- source = repo `kenshoushouri-cloud/boat-ai-v2`, branch `main`
- Cron = `20 23 * * *` = 08:20 JST
- start = `python -u research/candidate_discovery_v4_fallback_dispatcher.py`
- latest deploy `b44a67be-d9f0-4572-8ef6-5768dcf6d586` = **SUCCESS**
- deploy commit = current main `b26efcb...`
- service staged config = null

Production environment read-back:
- `stagedChanges=null`
- one empty-change pending EnvironmentPatch metadata entry was observed; do not accept/deploy it blindly. Re-read before any Production action.

Production PostgreSQL service:
- `postgres-recovery`
- id `aa4b9c32-f2bf-42c8-89b9-f5aac8d70fb3`
- latest service deployment = SUCCESS
- no plaintext variable values were read

## 5. Latest Production-derived historical readiness evidence

Latest Issue #42 read-only matched-readiness result:
- races / exact6 / fcount6 = **70,026**
- v4_base6 = **67,735**
- motor6 = **70,026**
- course_proxy6 = **58,287**
- opponent_replay = **56,599**
- reconstructed full core = **47,431 / 67.73%**
- complete_beforeinfo = **14,705**
- core_plus_beforeinfo = **7,936 / 11.33%**
- recent_form6 = **0**
- all_optional_inputs = **0**

This evidence is historical/read-only and gives **zero prospective gate credit**.

## 6. Last verified prospective baseline

Until a terminal 9/30 combined checkpoint is verified:
- V4 = **8/20** through 2026-09-28
- S03_M2 = **63/100** through the last verified checkpoint
- 2026-09-29 remains permanently unavailable

Never infer newer gate counts from settlement availability alone.

## 7. Next safe sequence

1. Preserve and verify the 2026-10-01 morning prospective cycle.
2. Continue read-only monitoring of `36667954064`; do not add a beforeinfo command.
3. Keep #526 Draft only until explicit merge approval.
4. When a dispatch route is available, run the canonical 9/30 combined checkpoint exactly once, read-only, after checking no existing terminal run exists.
5. After the morning prospective cycle, re-read the shared historical writer lane before any Opponent residual recovery.
6. Recover only verified residual ranges; never rerun whole completed campaigns.
7. Then proceed to recent_form, matched-readiness, and matched-contract backtest without outcome-guided tuning.

## 8. Handoff maintenance rule

Do not append new `LATEST OVERRIDE` blocks to `PROJECT_HANDOFF.md` or `CURRENT_STATE.md`.

Use:
1. `docs/HANDOFF_LATEST.md` as the tiny pointer.
2. One current compact `LIVE_HANDOFF_*.md` as the working handoff.
3. `docs/NEXT_CHAT_START_HERE.md` as the paste-ready startup note.
4. Git history / dated deep-history documents only when historical detail is required.

`CURRENT_COMPACT_HANDOFF / REFETCH_BEFORE_ACTION / ONE_OR_TWO_CHECKS / 929_UNAVAILABLE / V5_GATES_FIXED / PURCHASE_FALSE`
