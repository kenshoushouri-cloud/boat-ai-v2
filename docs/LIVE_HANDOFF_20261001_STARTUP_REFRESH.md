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
- `72733703cbe51f24b9bc55505159c241b4359335`
- PR #526 merged after current-main reconciliation and CI 6/6 SUCCESS

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
- `36703692641` = run-level read-back showed queued, but job-level read-back shows `2025-11-01..2025-11-30` **in_progress**
  - 2025-08/09/10 jobs are cancelled
  - later monthly jobs remain queued
  - together with `36667954064`, this means two old-head beforeinfo writers are active; add no new beforeinfo trigger

Old branch:
- `ops/command-aware-historical-concurrency-20260930-v2`
- exists, but compare against current main = **ahead 0 / behind 44**
- no unique changes remain; treat as superseded/inactive

Beforeinfo routing:
- #526 = **merged**
- merge SHA / current main = `72733703cbe51f24b9bc55505159c241b4359335`
- CI before merge = 6/6 SUCCESS
- old duplicate pending beforeinfo runs were replaced by no-write drain / invalid-range replacements
- existing active writers were not interrupted
- #528 and #529 remain closed without merge

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
- Railway-side log read-back confirms the database service is reachable and actively checkpointing
- this connector has no direct SQL execution path, so exact readiness counts below remain the latest canonical read-only Issue #42 workflow evidence
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
2. Continue read-only monitoring of `36667954064` and `36703692641`; do not add a beforeinfo command.
3. When a dispatch route is available, run the canonical 9/30 combined checkpoint exactly once, read-only, after checking no existing terminal run exists.
4. After the morning prospective cycle, re-read the shared historical writer lane before any Opponent residual recovery.
5. Recover only verified residual ranges; never rerun whole completed campaigns.
6. Then proceed to recent_form, matched-readiness, and matched-contract backtest without outcome-guided tuning.

## 8. Post-stabilization Railway cost optimization

User objective:
- if real-world operation becomes sustainably profitable, keep the current ChatGPT plan in principle
- reduce Railway cost after V5/backtest/operational-readiness work no longer needs the full historical dataset hot in Production

Recommended migration path:
1. Finish historical acquisition, matched-readiness, matched-contract backtest, and the V5 operational-readiness review first.
2. Create a complete PostgreSQL `pg_dump` archive (prefer custom format) and, where practical, a separate historical archive.
3. Store the archive outside Railway in durable S3-compatible/object storage.
4. Verify archive integrity with checksums plus schema/table/row-count checks, then perform a real restore test into an isolated scratch PostgreSQL instance.
5. Define the minimum Production hot-data retention needed for daily prediction, result settlement, monitoring, and near-term diagnostics.
6. Create a new smaller Railway PostgreSQL/volume and restore only the required hot dataset; do not assume an existing large volume can be downsized in place.
7. Switch Production only after read-only parity checks and explicit approval; keep the external historical archive restorable.
8. After stable operation is confirmed and actual resource usage fits the lower-tier limits, review Railway plan reduction (target candidate: Hobby) rather than keeping PRO solely for historical storage.

Latest storage snapshot at this handoff update:
- Railway workspace plan = **PRO**
- `postgres-recovery` is the only detected persistent volume-backed DB service
- attached volume provisioned size = **20 GB**
- measured database disk usage ≈ **4.95 GB**
- do not delete historical rows, volumes, backups, or change plan/DB configuration without explicit approval

Railway Agent cost-control rule:
- prefer deterministic Railway MCP reads such as status, service config, metrics, logs, and deployments for routine checks
- do **not** use Railway Agent for ordinary read-only/status investigation when those tools can answer the question
- use Railway Agent only when the normal Railway tools cannot obtain the required information and the expected value justifies its token cost
- keep any unavoidable Agent request narrowly scoped and read-only unless a separately approved mutation is required
- Railway Agent token charges consume the same plan included-usage pool as infrastructure usage, so minimizing Agent calls is part of the Railway cost-reduction plan

Principle: **archive first, prove restore, then shrink hot storage; minimize paid Agent usage before changing infrastructure.**

## 9. Handoff maintenance rule

Do not append new `LATEST OVERRIDE` blocks to `PROJECT_HANDOFF.md` or `CURRENT_STATE.md`.

Use:
1. `docs/HANDOFF_LATEST.md` as the tiny pointer.
2. One current compact `LIVE_HANDOFF_*.md` as the working handoff.
3. `docs/NEXT_CHAT_START_HERE.md` as the paste-ready startup note.
4. Git history / dated deep-history documents only when historical detail is required.

`CURRENT_COMPACT_HANDOFF / REFETCH_BEFORE_ACTION / ONE_OR_TWO_CHECKS / 929_UNAVAILABLE / V5_GATES_FIXED / PURCHASE_FALSE`
