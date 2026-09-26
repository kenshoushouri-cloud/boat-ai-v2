# V4 strict-prior-ST missing-information preregistration — 2026-09-27

Status: `RESEARCH_ONLY / PRE_RESULT / MORNING_SAFE / NO_ODDS / NO_RETUNE / NO_PRODUCTION_CHANGE`

## Why this is the next hypothesis

The completed #387 input ablation found no support for removing Course, Opponent,
Motor, or all enrichments. On the fixed current-V4 daily-rank-1 race, every
ablation worsened aggregate first-place LogLoss and Brier while head accuracy
remained unchanged.

The dominant current error is still first place:
- blocks 3–10 current-V4 daily-rank-1: 344 days;
- Top1 head accuracy 57.558%;
- first-place miss 41.3%.

Therefore the next preregistered question is missing first-place information.

## Frozen feature: strict-prior official ST

This experiment uses exactly one new input family.

For each target entry racer:
1. read only `v2_result_entries` rows whose source is `official_k_file`;
2. require `prior_race_date < target_date`;
3. deliberately exclude all same-day results, even for later target races;
4. choose the latest eligible prior official start timing for that racer;
5. apply the already-frozen July previous-ST rule:
   - ST <= 0.08: lane raw strength +0.08;
   - ST >= 0.18: lane raw strength -0.18;
   - otherwise 0;
   - missing: neutral 0.

No threshold, coefficient, lookback window, venue filter, race-number filter, or
availability threshold is searched in this experiment.

Using an earlier official result as a historical fact is allowed even if that row
was backfilled into PostgreSQL later: eligibility is determined by the official
race date, and only dates strictly before the target day are accepted.

## Frozen variants

Exactly two:
- `control`: current V4 unchanged.
- `strict_prior_st`: current V4 plus the fixed strict-prior-ST raw-lane adjustment.

Current V4 Course coefficient 0.50, Opponent coefficient 1.0, Motor beta 0.06,
temperature 2.20, structural selector, Top6 races and Top2 tickets stay unchanged.

## Evaluation

Same period and 10 chronological blocks as the canonical long-history run:
`2025-07-01..2026-09-22`.

Primary:
- Track A, fixed current-control daily-rank-1 race.
- first-place Top1 accuracy;
- first-place multiclass LogLoss;
- first-place multiclass Brier.

Secondary:
- formal Top2 trifecta hit rate / ROI / profit;
- Track B full variant reselection;
- rank1 and Top6 selector overlap.

Availability strata are fixed before results:
- `all`: missing ST is neutral;
- `any`: at least one of six lanes has strict-prior ST;
- `full6`: all six lanes have strict-prior ST.

The `all` Track A blocks 3–10 comparison is primary. Availability strata explain
coverage; they are not permission to invent a post-result filter.

## Leakage / safety contract

- PostgreSQL transaction READ ONLY.
- Load prior result-entry facts before target-day result access.
- Both variant distributions and selectors must freeze before querying target-day results.
- No target-day or same-day prior result is eligible for the feature.
- No odds / EV.
- No DB writes, LINE, candidate persistence, Railway settings, or purchase.
- `purchase_action=false`.

This history has already been inspected repeatedly. A positive retrospective result
is development evidence only. Any promising result must be followed by a fresh
first-write-wins prospective shadow before Production review.

`FIXED_TWO_VARIANT_FAMILY / STRICT_PRIOR_DATE / OFFICIAL_ST_ONLY / NO_SAME_DAY / NO_RETUNE / RESULT_AFTER_FREEZE / PURCHASE_FALSE`
