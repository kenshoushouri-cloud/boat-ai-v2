# V4 low-dimensional market-residual learner — 2026-09-23

Status: `RESEARCH_ONLY / PRETEST_TRAINED / 71R_FULLY_HELDOUT / MARKET_AS_BASELINE / NO_PRODUCTION_CHANGE`

## Motivation

The pre-test calibration audit found that, on 48 timing-safe races from
2026-07-01..2026-08-24, the best geometric market/current-V4 blend was
**beta=0.00 (market only)**.  The same market-only baseline remained better than
current V4 on the later 71-race held-out period.

Therefore another scalar blend is not useful.  The next question is narrower:

> are there small, stable structural errors in the market that can be learned
> before the held-out period?

## Fixed residual model

Market de-vigged probability is the offset.  The residual score has only 19
fixed features:

- clipped `log(current_V4_prob / market_prob)`;
- six first-lane indicators;
- six second-lane indicators;
- six third-lane indicators.

No venue/date/result/payout/odds-band feature is added.

Fixed optimization:

- 200 batch-gradient epochs;
- learning rate 0.10;
- L2 = 0.10;
- residual log-ratio clip = +/-3;
- zero initialization means the starting model is exactly the market.

There is **no hyperparameter search**.

## Time split

Calibration/training:

`2026-07-01..2026-08-24`

Held-out:

`2026-08-25..2026-09-22`

The fitted weights are frozen before the first held-out result is accessed.

## Profit test

On held-out races only:

- compare market, current V4 and residual model LogLoss/Brier/rank;
- rank all 120 tickets by residual probability × timing-safe observed odds;
- fixed point caps 2 / 3;
- fixed EV thresholds 1.00 / 1.05 / 1.10;
- flat 100 JPY per selected ticket;
- existing research candidate gate remains unchanged.

A historical pass is still only a Forward hypothesis and requires separate
prospective preregistration.

## Safety

`MARKET_OFFSET / 19D_FIXED_RESIDUAL / PRETEST_TRAINING_ONLY / HELDOUT_WEIGHTS_FIXED / NO_HYPERPARAM_SEARCH / READ_ONLY / NO_LINE / NO_BUY / PURCHASE_FALSE`
