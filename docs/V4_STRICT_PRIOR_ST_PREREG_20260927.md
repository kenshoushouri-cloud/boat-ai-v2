# V4 strict-prior-ST missing-information preregistration — 2026-09-27

Status: `RESEARCH_ONLY / COMPLETED / MORNING_SAFE / NO_ODDS / NO_RETUNE / NO_PRODUCTION_CHANGE`

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


## Completed read-only replay — canonical evidence

Canonical successful execution:

- trigger head: `bbcb65f11d6c9df59583557694682e02b27a3b24`
- workflow run: `36254658202` — SUCCESS
- artifact: `10910380430`
- artifact name: `v4-strict-prior-st-replay-36254658202`
- artifact ZIP SHA-256: `401d88781e81ada2777458f66cb0acb4e9de76a316a5faeaa0e94058ca9b9bda`
- result JSON SHA-256: `543d37c2d211aaa82bb0af6f37f4659a26db15c0e4c58d71e4d97e320c49e3bd`
- PostgreSQL transaction: READ ONLY
- prior official ST history: 374,619 rows / 1,649 racers
- secret enumeration: 0
- Production / LINE / purchase changes: none / `purchase_action=false`

Coverage:

- calendar days: 449
- control evaluated exact-six days: 432
- strict-prior-ST evaluated exact-six days: 434
- Track A pure-evaluation blocks 3–10: 344 control-fixed days
- Track A strict-prior-ST coverage: all 344 days had full6 prior-ST coverage

### Track A — fixed current-V4 daily-rank-1, blocks 3–10

| variant | days | head acc | LogLoss | Brier | formal Top2 | ROI | profit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 344 | 57.558% | 1.340703 | 0.655212 | 21.512% | 75.131% | -17,110 |
| strict_prior_st | 344 | 57.558% | 1.339431 | 0.654967 | 21.221% | 74.259% | -17,710 |

Paired interpretation:

- head correctness changed on **0 / 344** fixed races;
- LogLoss improved slightly in 6 of 8 pure-evaluation blocks and worsened in 2;
- Brier improved in 5 of 8 blocks and worsened in 3;
- aggregate LogLoss delta = **-0.001271**;
- aggregate Brier delta = **-0.000245**;
- this is a tiny confidence/calibration movement, not a first-place classification improvement;
- formal Top2 hit rate and ROI both worsened slightly.

### Track B — full variant reselection, blocks 3–10

| variant | days | head acc | LogLoss | Brier | formal Top2 | ROI | profit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 344 | 57.558% | 1.340703 | 0.655212 | 21.512% | 75.131% | -17,110 |
| strict_prior_st | 346 | 53.179% | 1.395238 | 0.676840 | 19.075% | 75.607% | -16,880 |

Selector overlap on common evaluable days:

- common days: 431
- rank1 overlap: 65.893% (284 / 431)
- mean Top6 overlap: 77.456%

The small fixed-race calibration gain does not survive the selector path. The
strict-prior-ST adjustment materially changes structural race selection and worsens
head accuracy, LogLoss, Brier, and Top2 hit rate. The small profit/ROI difference is
not treated as evidence for promotion because prediction quality worsened.

### Frozen conclusion

`STRICT_PRIOR_ST_NOT_MISSING_CLASSIFICATION_SIGNAL / FIXED_RACE_CALIBRATION_GAIN_TINY_ONLY / HEAD_CLASSIFICATION_CHANGED_0_OF_344 / FULL_RESELECTION_HEAD_AND_PROPER_SCORES_WORSE / DO_NOT_PROMOTE / NEXT_HYPOTHESIS_SHOULD_TARGET_MORNING_COURSE_ENTRY_UNCERTAINTY / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

This result does **not** support adding the feature to Production or starting a
prospective promotion shadow. The next missing-information investigation should
focus on information capable of changing the first-place ordering itself, with
morning course-entry uncertainty as the leading candidate.

## Execution deviations

Two implementation-only failures occurred after the hypothesis had been frozen:

1. run `36251669127` failed before the database replay because the pinned helper
   module was not registered in `sys.modules` before dataclass import.
2. run `36251763703` completed the read-only daily loop and target-result access
   but failed while assigning a variant-only final date to the canonical control
   blocks. No result JSON/hash or aggregate performance table was emitted. The
   observed failure was only the structural exception
   `date outside block bounds: 2026-09-22`.

Between those failures and the canonical run, no feature definition, threshold,
coefficient, period, selector, source rule, or interpretation gate changed. The
second fix copied the already-used #387 canonical rule that dates after the last
control-evaluable boundary belong to the final block. No performance metric from a
failed run was inspected or used to retune the experiment.

Only successful run `36254658202` and its immutable artifact are accepted as
scientific evidence.
