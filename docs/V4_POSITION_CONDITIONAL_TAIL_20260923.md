# V4 position-conditional tail model walk-forward — 2026-09-23

Status: `RESEARCH_ONLY / READ_ONLY_DB / CURRENT_SIX_FIXED / CURRENT_HEAD_FIXED / PRIOR_BLOCK_TRAINING_ONLY / NO_PRODUCTION_CHANGE`

## Motivation

Two completed long-history studies narrowed the remaining problem:

- changing the six-race structural selector did not improve unseen Top2 exact accuracy;
- statically amplifying national/local place2 information improved calibration but
  still reduced unseen Top2 exact accuracy;
- among current head-correct / Top2-miss races, most misses already occur at the
  first+second prefix.

The next test is therefore a genuinely position-conditional model rather than another
static coefficient boost.

## Fixed production control

The experiment does **not** change:

- current V4 probability model or coefficients;
- current equal-four six-race selector;
- current predicted first-place head;
- two formal tickets per race;
- Production behavior.

The challenger only changes ordering of lanes 2 and 3 after a first-place head has
already been fixed.

## Model

Two deterministic pairwise-logit models are maintained:

1. second-place model conditioned on the first lane;
2. third-place model conditioned on the first and second lanes.

Each candidate lane receives only pre-result, race-card features normalized within the
same race:

- current base raw strength;
- national win rate;
- national place2 rate;
- local place2 rate;
- faster-start score derived from avg ST;
- motor place2 rate;
- lane identity;
- relative lane position/distance to the conditioned first lane;
- and, for third place, relative position/distance to the conditioned second lane.

No odds, result-derived feature, payout, or future block statistic is a model input.

## Strict chronological walk-forward

The full 2025-07-01..2026-09-22 calendar is split into 10 chronological blocks.

- block 1 is warm-up only;
- the model is fixed for an entire test block;
- for each test date, current six races and both control/challenger Top2 tickets are
  frozen before official result/payout access;
- after the whole block has been evaluated, that block's now-historical outcomes are
  used for training;
- therefore a block can influence only later blocks.

Each historical training race is passed through the same fixed optimizer schedule.
There is no result-driven hyperparameter search.

## Primary metrics

Promotion evidence is based on unseen blocks 2-10:

- exact Top2 trifecta hit rate;
- first+second prefix hit rate conditional on the fixed head being correct;
- direct second-choice hit rate conditional on the fixed head being correct;
- consistency across chronological blocks.

ROI is secondary only and is not an optimizer target.

## Interpretation boundary

Even if the challenger improves historical unseen blocks, this run can only nominate
a separately preregistered prospective shadow. It cannot authorize Production model,
coefficient, selector, ticket-count, candidate-count, stake, LINE, or purchase changes.

`POSITION_CONDITIONAL / CURRENT_HEAD_FIXED / CURRENT_SIX_FIXED / FORMAL_2_POINTS / PRIOR_BLOCK_ONLY / RESULT_AFTER_FREEZE / NO_RETUNE / PURCHASE_FALSE`
