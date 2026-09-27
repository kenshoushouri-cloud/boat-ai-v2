# Research PR Registry — 2026-09-27

Purpose: reduce ambiguity from the large set of open Draft research PRs.

This registry does **not** close historical PRs. It defines which PRs are current decision sources and which are reference-only.

Always re-read current main / open PR heads / CI / Railway Production before acting.

## Tier A0 — main-integrated checkpoint entry points

### #425 / #426 — individual manual checkpoints
Main-integrated read-only refresh paths:
- #425: provider-selected immutable formal V4 checkpoint;
- #426: frozen S03_M2 checkpoint.

Both are `workflow_dispatch` only and unscheduled.

### #427 — frozen review-gate helper
Main-integrated pure status contract:
- V4: 10 / 20 / 30 resolved formal days;
- S03_M2: 100 evaluated observations;
- day-strength: >=10 future resolved days and >=3 KEEP / >=3 SKIP.

### #429 — combined manual Forward checkpoint
**Preferred operational refresh entry point.**

One manual run performs:
1. V4 provider inventory/arbitration before result access;
2. immutable artifact hash validation;
3. V4 read-only settlement;
4. frozen S03_M2 read-only checkpoint;
5. combined scorecard and existing review-gate status.

No schedule and no Production behavior change.

#409/#405 remain evidence-provenance sources; use #429 for routine refresh instead of creating new ad hoc checkpoint code.

## Tier A — current ROI / Forward decision sources

### #409 — formal V4 immutable-artifact settlement
Current role: **primary formal V4 economic evidence**.

Use for:
- provider-selected FORMAL_AVAILABLE inventory;
- immutable artifact settlement;
- formal TOP2 ROI / profit / robustness;
- 10 / 20 / 30 resolved-formal-day reviews.

Do not replace with historical candidate regeneration.

### #405 — S03_M2 prospective Forward
Current role: **secondary prospective economic evidence**.

Use for:
- 2026-09-13+ strict pre-deadline S03_M2;
- officially evaluated observations only;
- 100-observation review;
- stability / bootstrap / drawdown.

Do not use old pre-freeze profitability as support.

### #411 — future-only formal V4 day-strength shadow
Current role: **future skip/keep diagnostic only**.

Frozen:
- starts 2026-09-28;
- artifact-native TOP6 mean race_score;
- prior-seven FORMAL_AVAILABLE median reference;
- first 9/28 reference = 0.93817204;
- shadow label cannot change formal TOP6/TOP2.

## Tier B — active infrastructure / safety research

### #412 — fallback timing margin
Current role: **Production-change proposal preparation only**.

- 08:20 JST is the frozen preferred candidate;
- current Production Cron remains 08:25 JST;
- activation is constrained to cronSchedule only;
- explicit approval required before any Railway change.

### #422 — common prospective Forward economics integrated
Current role: **main-integrated common pure economic semantics**.

Now on main:
- evaluated = investment-bearing settlement;
- invalid_result = void / zero-investment;
- pending = zero-investment;
- common ROI, DD, losing streak, largest-hit share, halves and bootstrap;
- normalization of immutable V4 official/non-official settlement into the same semantics.

### #423 — common economics validation suite integrated
Current role: **main-integrated exact validation suite**.

Contains the already-green read-only audits for:
- existing N02/S03 semantics parity;
- formal V4 TOP2 parity;
- frozen S03_M2 parity.

Historical stacked PRs #415/#416/#419/#420 are closed as superseded; their comments/runs remain provenance.

## Tier C — F-count future activation path

Dependency chain:
- #397 — prospective head-error diagnostic preregistration;
- #398 — separate hash-bound F-count companion contract;
- #400 — exact-36-row pure adapter;
- #413 — actual current formal-artifact compatibility + future activation manifest.

Current status:
- technical preparation is green;
- actual F-count DB read / companion persistence / scheduling is **not approved**;
- historical backfill and historical F-count coefficient search remain forbidden.

These PRs should be read as one dependency chain, not independent promotion candidates.

## Tier D — evidence correction / deprioritized tracks

### #406 — historical S03 robustness / correction
Role: **negative evidence / correction source**.

Current interpretation:
- old pre-freeze S03 profitability support is rejected;
- do not use it to justify S03 promotion.

### #408 — S02 Forward
Role: **deprioritized prospective track**.

Current evidence is economically weak. Do not widen gates to rescue it.

### #407 — GUARD05 Forward
Role: **deprioritized until natural affected observations exist**.

Affected evaluated rows were zero at latest review. Do not loosen the frozen guard to manufacture affected cases.

## Tier E — input-readiness supporting research

- #394 — recent_form readiness: not ready / fail closed.
- #395 — unused pre-race entry information inventory.
- #396 — input-only novelty audit: F-count shape-ready; L-count degenerate.

These support future feature decisions but are **not current ROI promotion evidence**.

## Tier F — legacy exploration / historical research

PRs #376 through #393, except any specifically promoted above, are retained for reproducibility/history.

Examples include:
- historical 1-5 point walk-forward;
- selector-rank diagnostics;
- alpha025 shadows;
- timing-safe profit-gate exploration;
- economic/structural rerank preregistrations;
- daily 1-3 / daily-one-race preregistrations;
- input ablation / ST / course-movement / exhibition research.

Rule:
**do not treat these as current decision sources merely because the PR remains open.**
Only reactivate one with a new explicit preregistration or a later handoff override.

## Current reading order

For ROI work:
1. main handoff/current-state;
2. main-integrated #429 combined manual checkpoint for refresh;
3. #409 V4 evidence provenance;
4. #405 S03_M2 evidence provenance;
5. #411 future-only day-strength shadow;
6. main-integrated #422/#423 common economics/validation suite.

For operational safety:
1. #412;
2. #409 provider inventory/freeze contract.

For F-count:
1. #397;
2. #398;
3. #400;
4. #413.

## Cleanup policy

Do not mass-close research PRs solely for tidiness. Historical Drafts preserve preregistration and evidence provenance.

A PR may be closed later when:
- a newer PR explicitly supersedes its contract;
- its evidence is recorded in main docs;
- no active stacked PR depends on its branch.

Until then, use this registry to avoid reference ambiguity.

`CHECKPOINT_MAIN_425_426_427_429 / EVIDENCE_409_405_411 / COMMON_ECON_MAIN_422_423 / FALLBACK_PREP_412 / FCOUNT_CHAIN_397_398_400_413 / DEPRIORITIZED_406_407_408 / LEGACY_REFERENCE_ONLY_376_393`
