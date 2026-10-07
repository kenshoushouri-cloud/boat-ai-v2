# V5 zero-base feature ablation plan — 2026-10-08

## Purpose
Build V5 from zero without inheriting V4 prediction inputs, weights, gates, selectors, or feature admission decisions.

Production remains V4 until a separately approved promotion decision.

## Data reuse rule
Raw factual data already collected for V4 may be reused as source data.
Do not reuse V4 predictions, coefficients, thresholds, derived scores, feature weights, selector logic, or "already accepted" feature decisions.

Formal evaluation period:
- 2025-07-01 through 2026-10-05

Hard rules:
- research-only
- no Production model change
- no LINE / purchase / stake change
- no target-race outcome leakage
- same time split for every comparison
- no post-outcome tuning
- CPU/RAM/Network cost minimized

## B0 — true zero baseline
The first V5 baseline contains no racer, motor, venue, course, weather, exhibition, recent-form, or opponent information.

For six starters:
- first-place probability = 1/6 each
- probability metrics only
- no betting/ROI conclusion is taken from B0 ties

B0 exists only to measure whether each information family contains predictive value.

## Feature-family admission method

Each family is tested in two ways.

### Test A — standalone value
Compare:
- B0
- B0 + one feature family only

This measures whether that information has predictive value by itself.

### Test B — incremental value
After one or more families are accepted, compare:
- current accepted set
- current accepted set + one candidate family

This prevents feature admission from depending only on test order.

A feature family is not admitted merely because it was useful in V4.

## Initial test order
Order is for execution efficiency only, not automatic admission priority.

1. lane / course
2. racer base ability
   - class
   - national win/place performance
3. local / venue racer performance
4. start performance
   - average ST and related pre-race historical ST only
5. motor performance
6. racer recent form
7. racer-course compatibility
8. opponent / field-strength information
9. exhibition ST
10. exhibition time
11. weather / water conditions
12. season / time-of-year effects
13. F-count / L-count and other status information
14. remaining collected-but-not-yet-admitted information

Each family should be separable enough that removing it produces an interpretable comparison.

## Evaluation
Primary probability metrics:
- LogLoss
- Brier score
- top-1 accuracy / calibration checks

Secondary decision metrics are evaluated only after probability value is demonstrated:
- hit rate
- ROI
- profit
- stability by time split / venue / period

No feature is accepted solely because of one ROI spike.

## Admission outcome
Each family receives one status:
- KEEP: repeatable out-of-sample improvement with acceptable stability/cost
- HOLD: uncertain, interaction-only candidate, or insufficient evidence
- REJECT_INPUT: worsens or does not improve prediction enough to justify complexity/cost

REJECT_INPUT means "do not use as V5 model input".
It does not mean delete the underlying collected data.

## Interaction pass
Only after first-pass family screening:
- test interactions among KEEP/HOLD families
- examples: motor x exhibition, lane/course x weather, racer x venue
- no unrestricted combinatorial search

## Stop condition for V5 core
V5 core is the smallest accepted feature set that:
- materially beats B0 and earlier accepted sets
- remains stable across the fixed historical splits
- has no leakage
- has acceptable CPU/RAM/Network cost

Only after this zero-base V5 core is frozen should selector/ticket optimization begin.

## Supersession
This plan supersedes the V5 feature-admission assumptions in:
- docs/V5_RESEARCH_SCOPE_LOCK_20260927.md

That older file remains historical evidence only.
It must not be used to pre-admit V4 feature families into the new V5.

`V5_ZERO_BASE / RAW_DATA_REUSE_ONLY / NO_V4_FEATURE_INHERITANCE / ONE_FAMILY_AT_A_TIME / NO_LEAKAGE / RESEARCH_ONLY / COST_MINIMIZE`
