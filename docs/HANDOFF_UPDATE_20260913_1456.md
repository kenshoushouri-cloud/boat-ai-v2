# Handoff update — 2026-09-13 14:56 JST

This document records only facts verified after the prior handoff check. It does not replace `docs/CURRENT_STATE.md`, `docs/PROJECT_HANDOFF.md`, or `docs/PROJECT_HISTORY.md`.

## Verified GitHub state

- current `main`: `8abbb0186852969129175848ee106118031f97e4`
- PR #351 `Research: Candidate Discovery main feed (V1-V4)` remains open and is not Draft.
- PR #351 current head: `84b0c3df089314851246e291fa606cd20a5ba1f9`
- The PR records a pre-result Forward freeze for 2026-09-13 at about 08:44 JST: 180/180 races evaluable, new-system core 6 races / 12 tickets, legacy carryover 2 races / 2 tickets, total 8 races / 14 tickets.
- Historical V1-V3 ROI remains below 100%; this is not purchase approval or profitability proof.
- Latest head CI verified SUCCESS for 12 related workflows, including Candidate Discovery Main Feed, System Audit, V4 Pure Contract, Late Bao Pure Contract, K Payout Probe, Bet-Type contracts/audits, Production shadow isolation, Python syntax, V21 parser sanity, and mojibake guard.
- Production promotion remains a separate explicit approval boundary.

## Verified Railway read-only state

Project `boat-v2-postgres` production:
- environment reports `stagedChanges=null`; this is not evidence that older staged changes were reviewed or safely applied.
- `postgres-recovery`: SUCCESS, 1 replica.
- `cron-opponent-pressure-v2-live`: Cron `0 22 * * *`, latest deployment SUCCESS.
- `cron-opponent-pressure-v2-runner`: latest deployment FAILED.
- major existing production Cron services currently report SUCCESS.
- storage one-shot/audit services exist and report successful latest deployments, but this handoff run did not execute or rerun them.

## Safety / unresolved boundaries

No Production model, coefficient, threshold, DB schema/data, LINE, purchase behavior, Railway variable/config/Cron, staged patch, or PR merge was changed by this handoff run.

PR #351 remains research/Forward evidence only. Forward freeze success, CI success, and candidate-count expansion must not be interpreted as profitability, ROI approval, or Production promotion.
