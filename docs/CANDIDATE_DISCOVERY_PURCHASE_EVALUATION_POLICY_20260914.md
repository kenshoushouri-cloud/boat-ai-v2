# Candidate Discovery Purchase Evaluation Policy — 2026-09-14

## Purpose

Freeze the evaluation policy for the new Candidate Discovery path before prospective V4 evidence accumulates. The goal is to avoid two opposite failure modes:

1. reproducing the old-system behavior where eligible days frequently expose no useful candidates because the selector is too narrow;
2. forcing purchases merely to keep activity high or to hit a daily/monthly profit target.

This document is research/evaluation policy only. It does not change Production selector logic, thresholds, model coefficients, Railway, DB, LINE, Forward persistence, or purchase behavior.

## Stage 1: candidate availability

The fixed V4 Stage-1 contract remains unchanged:

- 6 races/day
- TOP2 exact-order trifecta per race
- 12 core tickets/day on an eligible complete-data day
- Course coefficient 0.50, missing lane neutral
- Opponent Pressure coefficient 1.0, first-place only
- Motor2 beta 0.06, position weights 1.0 / 0.6 / 0.3
- 4 structural metrics equal-weight daily rank
- no Stage-1 EV gate
- no absolute odds gate
- purchase_action=false

Interpretation:

- 6 races / 12 tickets is a ranked candidate feed, not a purchase quota.
- On a timing-safe complete-data day, Stage 1 should continue to expose the ranked feed instead of collapsing into an old-system-style chronic zero-candidate outcome.
- If source completeness or timing safety fails, fail-closed takes priority; an invalid/missed day is not reclassified as a legitimate zero-candidate day.
- Do not lower research thresholds after outcomes merely to increase candidate counts.

## Stage 2: corroboration, not candidate deletion

The frozen Stage-2 hypothesis remains:

- MKT_LATE07_TOP2_SUPPORT_V1
- timing-safe market TOP2 support at deadline 0..7 minutes
- Stage 2 does not remove or rerank Stage-1 candidates
- exact prospective milestones: 30 / 50 / 100 supported evaluated cases
- no post-outcome retuning

Stage 2 is evidence for a later purchase-decision layer, not permission to rewrite the Stage-1 feed after results are known.

## Purchase-count policy

Future BUY count should be variable and evidence-driven.

Allowed conceptually for later evaluation:

- strong day: multiple BUYs if evidence supports them;
- ordinary day: fewer BUYs;
- weak day: one or zero BUYs;
- WATCH/ranked candidates may remain visible even when BUY=0.

Not allowed:

- buying all 12 tickets solely because they were generated;
- adding tickets until a daily profit target is reached;
- loosening thresholds after losses;
- raising stake because the month is behind target;
- reconstructing missed prospective evidence after results.

A no-BUY day can be valid. A chronic no-candidate Stage-1 feed on otherwise eligible complete-data days is a separate product-quality problem and should be measured separately from BUY selectivity.

## Profit objectives

Profit objectives are evaluation targets, not selector optimization constraints.

Current operating references:

- base monthly reference: +30,000 JPY
- stretch monthly reference: +50,000 JPY
- no mandatory daily +1,000 JPY rule

Do not tune coefficients, thresholds, candidate logic, or stake sizes to force these targets before adequate prospective evidence exists.

## Metrics to report prospectively

Keep candidate availability and purchase quality separate.

Candidate-feed metrics:

- eligible complete-data days
- valid prospective freeze days
- Stage-1 races/day
- Stage-1 tickets/day
- missed/invalid days and exact fail-closed reason
- chronic-zero-candidate rate on otherwise eligible days

Purchase-layer evaluation metrics, once a frozen rule exists:

- BUY tickets/day
- no-BUY-day rate
- investment
- return
- profit
- ROI
- hit rate
- average payout per hit
- maximum drawdown
- maximum losing streak
- monthly investment and monthly profit

Always keep BASELINE, V4 prospective, historical replay, and Production evidence separate.

## Stake-size boundary

Until enough prospective evidence exists, evaluate ticket quality using fixed-unit accounting first. Variable stake ideas such as 100/200/300 JPY or S/A/B sizing remain research-only.

Any future variable-stake Production rule requires a separate predeclared experiment and explicit Production approval. Do not infer that scaling stake linearly will preserve realized ROI, drawdown, liquidity, or user risk tolerance.

## Decision gate

Do not promote a purchase rule from candidate visibility alone.

The desired end state is:

- broad enough Stage-1 ranked candidates to avoid old-system-style chronic inactivity;
- selective, timing-safe, evidence-backed BUY decisions;
- zero forced purchases;
- no daily-profit chasing;
- monthly +30,000 JPY as a base evaluation reference and +50,000 JPY as a stretch reference only after sufficient prospective evidence;
- fail-closed and purchase_action=false preserved throughout research.

Current classification:

`RESEARCH_POLICY_FROZEN / CANDIDATE_FEED_NOT_PURCHASE_QUOTA / AVOID_CHRONIC_ZERO_CANDIDATE_ON_ELIGIBLE_DAYS / VARIABLE_BUY_COUNT_ALLOWED_LATER / ZERO_BUY_DAY_ALLOWED / NO_DAILY_PROFIT_CHASING / MONTHLY_30K_BASE_50K_STRETCH / NO_THRESHOLD_OR_STAKE_RETUNE_BEFORE_PROSPECTIVE_EVIDENCE / NO_PRODUCTION_CHANGE`
