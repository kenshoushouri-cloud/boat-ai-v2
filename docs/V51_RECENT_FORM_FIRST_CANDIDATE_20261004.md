# V5.1 first candidate — Recent Form 5-race

## Status
- research-only; Production=V4 unchanged; frozen V5 core unchanged.
- Candidate is preregistered before its V4/V5 incremental outcome evaluation.

## Candidate
`V51_RECENT_FORM_LAST5_TOP3_V1`

Source:
- existing `v2_race_entries.recent_form` reconstructed from `official_k_file` only;
- each target race may use only races from strictly earlier calendar dates;
- same-day earlier race results are excluded;
- maximum 5 prior races per racer;
- no target-race result, payout or odds in feature construction.

Raw lane feature:
- `recent_top3_rate_5 = top3 finishes / valid prior finishes`;
- valid prior finish = numeric finish_position in 1..6;
- minimum prior valid finishes = 3;
- fewer than 3 valid finishes => missing/neutral, never imputed from current aggregates.

Normalization:
- within each target race, z-score `recent_top3_rate_5` across lanes that have the feature;
- if fewer than 2 lanes have a valid feature or standard deviation is zero, the entire recent-form effect is neutral.

Model integration protocol:
- baseline remains the frozen V4/V5 probability contract;
- coefficient is fit **once using TRAIN_REFERENCE only (2025-07-01..2025-12-31)** with a bounded one-parameter search declared before VALIDATION/OOS are read;
- after coefficient freeze, no retuning in VALIDATION (2026-01..06) or OOS (2026-07..09);
- first evaluation target is probability quality (LogLoss/Brier/calibration); economics is secondary;
- feature is rejected/held if improvement is not directionally consistent in VALIDATION and OOS;
- even if historical evidence passes, prospective Forward reproduction is required before any Production review.

## Comparison discipline
- same race set and same frozen baseline wherever data coverage permits;
- report coverage and missingness separately;
- no venue/race-band filters invented after outcomes;
- no Course-complete-only or other post-hoc gating;
- no odds/EV selector change;
- no automatic promotion.

## Why first
- racer ability, Motor2 and Racer Course are already represented in V4/V5;
- recent short-term condition is not yet part of the frozen core;
- historical recent_form is already reconstructed through 2026-09-30 under a prior-day no-leakage contract;
- the latest Exhibition ST Forward checkpoint (run 37185447967) had 2,050/2,050 valid evaluations but slightly worsened overall tri LogLoss/Brier/rank, so Exhibition ST is not the first adoption candidate.

`V51_RF5_TOP3 / PRIOR_DAY_ONLY / TRAIN_FIT_ONCE / VALIDATION_OOS_NO_RETUNE / FORWARD_REQUIRED / PROD_UNCHANGED`

## Coefficient search lock

Frozen in `docs/V51_RECENT_FORM_COEFFICIENT_SEARCH_LOCK_20261004.md`.
TRAIN-only grid selection must follow that document exactly before VALIDATION/OOS are read.
