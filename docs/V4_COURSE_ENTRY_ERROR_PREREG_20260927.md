# V4 course-entry error attribution preregistration — 2026-09-27

Status: `RESEARCH_ONLY / PRE_RESULT / ERROR_ATTRIBUTION_ONLY / NO_PREDICTOR_CHANGE`

## Question

Are current V4 daily-rank-1 first-place errors concentrated in races where the
official actual start course differs from the assigned boat/lane?

This is a causal-diagnostic step before proposing any new morning feature.
Actual start course is known only at/after the race start and is therefore
**forbidden as a predictor input** here.

## Frozen population

Replay the unchanged current V4 long-history contract for
`2025-07-01..2026-09-22`, 10 canonical blocks, source cutoff 08:15 JST.
Require the canonical 432 exact-six control days.

For each day's already-frozen control daily-rank-1 race, and only after the
selection is frozen:
- query the official result;
- query `v2_result_entries` with source `official_k_file`;
- require six lanes and a one-to-one actual start-course permutation 1..6.

## Frozen strata

Blocks 3–10 are the main diagnostic period.

Exactly these descriptive strata:
- no course change / any course change;
- predicted head boat did not move / moved from its assigned course;
- lane 1 not displaced / displaced;
- actual winner did not move / moved.

Metrics are count, head accuracy, multiclass LogLoss, and Brier.
No threshold search, coefficient fit, odds, EV, candidate filter, or Production
change is allowed.

## Interpretation

A large and directionally coherent error concentration would justify a separate
future hypothesis using **strictly prior** racer course-entry tendency as a
morning-safe predictor. It would not justify using actual course itself and would
not authorize Production.

If errors are not meaningfully concentrated in these strata, course-entry
uncertainty should not be promoted as the next missing-information direction.

`FREEZE_CURRENT_V4 / ACTUAL_COURSE_OUTCOME_DIAGNOSTIC_ONLY / RESULT_AFTER_SELECTION_FREEZE / NO_RETUNE / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`
