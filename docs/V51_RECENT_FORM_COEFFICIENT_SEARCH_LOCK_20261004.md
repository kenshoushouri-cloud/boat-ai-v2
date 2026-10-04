# V5.1 Recent Form coefficient search lock — 2026-10-04

## Status

Pre-outcome preregistration for `V51_RECENT_FORM_LAST5_TOP3_V1`.
No TRAIN/VALIDATION/OOS outcome metric has been inspected under this candidate before this lock.

Production V4 and frozen V5 remain unchanged.

## Frozen population

Use only the already audited shared population where:
- exact six race-entry lanes exist;
- six-lane Motor2 is complete, matching the frozen V4/V5 comparison population;
- Recent Form is evaluable under `V51_RECENT_FORM_LAST5_TOP3_V1`.

Frozen readiness counts from run `37187444850`:
- TRAIN_REFERENCE: **26,801**
- VALIDATION: **28,178**
- OOS: **14,492**
- total shared/evaluable: **69,471**

Course missing remains neutral.
Opponent missing remains neutral.
No post-outcome population filtering is allowed.

## Frozen transform

For each lane:
1. From at most five strictly-prior-calendar-day `official_k_file` records, retain numeric finish positions 1..6.
2. Require at least 3 valid finishes.
3. Compute `recent_top3_rate_5 = top3_count / valid_finish_count`.
4. Within race, z-score only valid lane values.
5. Missing lane z = 0 (neutral).
6. If fewer than 2 valid lanes or population standard deviation is zero, Recent Form effect for the entire race is neutral.

Integration point:
- start from frozen V4 `course_adjust_raw(base_raw, course_top3)`;
- add `RECENT_FORM_COEF * recent_form_z[lane]` to each lane raw score;
- then run the frozen V4 lane-probability, Opponent first-place-only adjustment, trifecta construction, and Motor2 adjustment unchanged.

No selector, odds, EV, Course, Opponent, Motor2, ticket-count, or stake rule changes are part of this candidate.

## Coefficient grid — frozen

Evaluate exactly these 11 values on TRAIN_REFERENCE only:

`[-0.50, -0.40, -0.30, -0.20, -0.10, 0.00, 0.10, 0.20, 0.30, 0.40, 0.50]`

Do not:
- add intermediate values after seeing TRAIN;
- expand beyond ±0.50 after seeing TRAIN;
- search venue-specific, month-specific, lane-specific, or class-specific coefficients;
- combine another new feature in this coefficient search.

If a boundary value (-0.50 or +0.50) wins, freeze that boundary value as-is. Do not extend the grid in this candidate version.

## TRAIN fit rule — frozen

TRAIN_REFERENCE = 2025-07-01..2025-12-31 only.

Primary objective:
- minimize mean official trifecta multiclass LogLoss over the frozen TRAIN population.

Tie handling:
1. treat objective values within `1e-12` as tied;
2. choose the smaller absolute coefficient;
3. if still tied, choose the smaller numeric coefficient.

The coefficient is frozen immediately after TRAIN selection and recorded with:
- candidate ID;
- exact grid;
- TRAIN population count;
- chosen coefficient;
- baseline/coefficient TRAIN metrics;
- artifact SHA256.

If `0.00` wins, the candidate is **REJECT/HOLD** and VALIDATION/OOS need not be used for adoption testing.

## Blind VALIDATION/OOS adoption gate — frozen

After the TRAIN coefficient is frozen, evaluate it without retuning on:
- VALIDATION = 2026-01-01..2026-06-30
- OOS = 2026-07-01..2026-09-30

For both VALIDATION and OOS independently, versus coefficient 0.00 baseline:
1. mean trifecta LogLoss must be strictly lower;
2. multiclass Brier score must be strictly lower;
3. mean rank of the official trifecta must not worsen.

All three conditions must pass in **both** periods.

Additional diagnostics to report but not use for coefficient retuning:
- probability assigned to official trifecta;
- top-1 / top-2 ticket hit rate;
- calibration bins;
- daily/monthly stability;
- missing/neutral counts.

A failure in either VALIDATION or OOS means **do not adopt this Recent Form feature** into V5.1. Continue collecting Recent Form for future research.

## Forward gate

Historical pass is research evidence only.
Before any Production review:
- freeze the historical coefficient unchanged;
- collect prospective pre-race Recent Form evidence;
- require Forward probability-quality reproduction;
- Production activation still requires explicit human approval.

## Safety

- no odds/EV feature;
- no target outcome in feature construction;
- no post-hoc gate/venue/race-band filtering;
- no DB write required for coefficient evaluation;
- no Production/LINE/purchase/stake change;
- current V4/V5 live gates remain independent.

`V51_RF_COEF_GRID_LOCK_V1 / GRID_11_NEG050_TO_POS050 / TRAIN_LOGLOSS_ONLY / BLIND_VAL_OOS / NO_RETUNE / FORWARD_REQUIRED`
