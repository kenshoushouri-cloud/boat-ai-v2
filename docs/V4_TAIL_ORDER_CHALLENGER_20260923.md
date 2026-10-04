# V4 tail-order challenger walk-forward — 2026-09-23

Status: `RESEARCH_ONLY / READ_ONLY_DB / CURRENT_SIX_FIXED / FIRST_MARGINAL_FIXED / NO_PRODUCTION_CHANGE`

## Why this follows the selector study

The long-history selector study found a consistent tradeoff:

- formulas emphasizing `head_p1` / `head_margin` can improve first-place correctness;
- the same formulas do not improve exact trifecta Top2 correctness in past-only walk-forward.

The current-control long-history decomposition also shows that, among races where
the first-place head is correct but formal Top2 misses, the larger error bucket is
already at the first+second prefix rather than only the third-place completion.

This experiment therefore leaves race selection and first-place probability untouched
and tests only second/third ordering.

## Fixed control

Unchanged:

- current V4 model and coefficients;
- current daily equal-four selector;
- exact six races/day;
- formal two tickets/race;
- current first-place probability marginal for every lane.

## Preregistered tail family

Nine candidates are fixed before result access.

Control has no extra tail reweight.

Eight challengers add a bounded signal built from the within-race z-scores of:

- national place2 rate;
- local place2 rate.

The two z-scores are averaged, then applied only to ticket positions 2 and 3.
The candidate family varies the fixed boost and the second-vs-third positional weight.

Reweighting is normalized **within each first-place head**, so the total probability
mass of every first-place lane is mathematically preserved. This makes the experiment
about tail order only, not a hidden first-place retune.

## Timing and walk-forward

For each date:

1. build current V4 distributions from timing-safe pre-result inputs;
2. select the current exact six races;
3. freeze every candidate's Top2 tickets for those same races;
4. only then read official result/payout;
5. evaluate all candidates on the identical six-race sample.

The 10-block adaptive comparison uses block 1 only as warm-up. Before each later
block it chooses a candidate using prior evaluated days only:

- primary: Top2 exact-hit rate;
- tie-break: lower mean log loss;
- final deterministic tie-break: candidate name.

ROI is secondary and is never used for candidate selection.

## Interpretation boundary

Historical evidence can nominate a prospective tail-order shadow only. It cannot
authorize coefficient changes, Production model changes, ticket-count changes,
candidate-count changes, or purchase behavior.

`TAIL_ONLY / HEAD_MARGINAL_PRESERVED / CURRENT_SIX_CONTROL / FORMAL_2_POINTS / PAST_ONLY_CHOICE / NO_RETUNE / PURCHASE_FALSE`
