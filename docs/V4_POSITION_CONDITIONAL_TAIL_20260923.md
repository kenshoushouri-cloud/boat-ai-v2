# V4 position-conditional tail model walk-forward — 2026-09-23

Status: `RESEARCH_ONLY / READ_ONLY_DB / CURRENT_SIX_FIXED / FIRST_PLACE_MARGINAL_FIXED / PRIOR_BLOCK_TRAINING_ONLY / NO_PRODUCTION_CHANGE`

## Motivation

Completed long-history studies narrowed the remaining problem:

- changing the six-race structural selector did not improve unseen Top2 exact accuracy;
- static place2 amplification improved calibration but reduced unseen Top2 exact accuracy;
- most current head-correct / Top2 misses already fail at the first+second prefix.

The next test is a genuinely position-conditional model.

## Important contract correction

The initial v1 attempt incorrectly assumed that the current formal Top2 tickets always
share one first-place head. That is not guaranteed after the full V4 distribution,
including Motor adjustment, is ranked.

The corrected v2 contract therefore does **not** force one head.

Instead it preserves the complete current first-place marginal distribution exactly:

`P_challenger(first) = P_current(first)`

and learns only:

- `P(second | first)`;
- `P(third | first, second)`.

The challenger ticket distribution is their product. This is a cleaner tail-only test
because any current Top2 mixture across first-place heads remains possible.

## Fixed production control

The experiment does not change:

- current V4 model or first-place marginal;
- current equal-four six-race selector;
- two formal tickets per race;
- Production behavior.

## Model

Two deterministic pairwise-logit models use only pre-result race-card features,
normalized within the same race:

- current base raw strength;
- national win rate;
- national place2 rate;
- local place2 rate;
- faster-start signal from avg ST;
- motor place2 rate;
- lane identity;
- relative lane position/distance to the conditioned first lane;
- and, for third place, relative position/distance to the conditioned second lane.

No odds, payout, result-derived feature, or future block statistic is an input.

## Strict chronological walk-forward

2025-07-01..2026-09-22 is split into 10 chronological blocks.

- block 1 is warm-up only;
- model weights are fixed for an entire test block;
- each day freezes current six races, current Top2, challenger Top2, and the
  challenger's second choice for every possible first lane before result access;
- results are then read for evaluation;
- only after the whole block is complete can its outcomes update the model;
- a block therefore influences only later blocks.

Hyperparameters are fixed in the workflow; there is no result-driven search.

## Primary metrics

On unseen blocks 2-10:

- exact formal Top2 trifecta hit rate;
- first+second prefix hit rate when the current top first-place marginal is correct;
- conditional second-choice hit rate evaluated using the actual first lane, where
  choices for all possible first lanes were frozen pre-result;
- chronological block consistency.

ROI remains secondary and is never an optimizer target.

## Interpretation boundary

Even a positive historical result can only nominate a separately preregistered
prospective shadow. It cannot authorize Production model/coefficient/selector,
ticket-count, candidate-count, stake, LINE, or purchase changes.

`POSITION_CONDITIONAL / FIRST_PLACE_MARGINAL_PRESERVED / CURRENT_SIX_FIXED / FORMAL_2_POINTS / PRIOR_BLOCK_ONLY / RESULT_AFTER_FREEZE / NO_RETUNE / PURCHASE_FALSE`
