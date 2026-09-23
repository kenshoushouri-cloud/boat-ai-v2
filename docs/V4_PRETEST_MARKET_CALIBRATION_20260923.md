# V4 pre-test market calibration — 2026-09-23

Status: `RESEARCH_ONLY / PRETEST_CALIBRATION / FULL_71R_HELDOUT / CURRENT_V4_ONLY / NO_PRODUCTION_CHANGE`

## Purpose

The longer result-free odds coverage found 119 current-V4 selected races with
coherent complete 120-ticket odds observable by deadline minus five minutes over
2026-07-01..2026-09-22.

This permits a cleaner market-relative test:

- calibrate market/model blend strength using **only 2026-07-01..2026-08-24**;
- evaluate profitability on the entire **2026-08-25..2026-09-22** sample.

The alpha0.25 tail model is not used in calibration because its historical training
cutoff is later than some calibration dates. Only current V4 is used, avoiding
future leakage.

## Calibration

Fixed beta grid:

- 0.00 market only;
- 0.10;
- 0.25;
- 0.50;
- 1.00 current V4 only.

Beta is selected solely by calibration multiclass LogLoss, then Brier, then smaller
beta. Calibration ROI is not used.

## Held-out value test

The chosen beta is frozen before any held-out result is considered.

On the full 2026-08-25..2026-09-22 timing-safe sample, report:

- market / selected blend / current V4 LogLoss, Brier and actual-ticket rank;
- market Top2/Top3 economics;
- selected-blend market-relative EV top 2/3 tickets at fixed EV thresholds
  1.00 / 1.05 / 1.10;
- chronological halves, largest-hit concentration, drawdown and day bootstrap.

A historical candidate still requires the existing gate and a new prospective
preregistration. No held-out outcome may change beta or thresholds.

## Safety

`PRETEST_ONLY_CALIBRATION / CURRENT_V4_ONLY / HELDOUT_71R / BETA_NOT_PROFIT_SELECTED / READ_ONLY / RESULT_AFTER_FREEZE / NO_LINE / NO_BUY / PURCHASE_FALSE`
