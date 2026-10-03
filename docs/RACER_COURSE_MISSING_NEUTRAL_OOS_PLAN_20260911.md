# Racer Course missing-row neutral fallback OOS plan — pre-registered 2026-09-11 JST

Status: `RESEARCH_ONLY / FIXED_RULE / NO_PRODUCTION_CHANGE`

## Question

Can races currently blocked only because one or more exact `(racer_number, race_date, course=lane)` Course Top3 rows are unavailable be evaluated safely by leaving those missing lanes at the current v24 BASE strength while applying the already-fixed Course coefficient only to timing-safe observed lanes?

This plan is frozen before reading outcome metrics from the new missing-row evaluation.

## Fixed inputs

- BASE: current v24 PRE raw strength/probability logic, unchanged.
- Course feature: official racer-by-course Top3 rate only.
- Course coefficient: **0.50 fixed** from the previously validated train-only study. No new coefficient search.
- Early-PRE course proxy: lane = course.
- Snapshot source must be exact race date.
- A Course row is usable only when Top3 is finite and in `[0,100]`, `created_at <= 08:15 JST`, and `created_at < race deadline`.
- Late, wrong-date, missing, malformed, or absent rows are treated as unavailable, never repaired from later data.

## Fixed missingness rule

For each race with exactly six valid v24 entries:

1. Collect timing-safe observed Course Top3 values by lane.
2. If at least two observed values exist and their standard deviation is non-zero, z-score **only the observed values** using the observed-lane mean/SD.
3. Missing/unusable lanes receive Course z = **0**, meaning their v24 BASE raw strength is unchanged.
4. Observed lanes receive `BASE raw strength + 0.50 * observed-lane z`.
5. If fewer than two usable values exist or observed SD is effectively zero, all Course adjustments are zero and the race equals BASE.
6. No post-outcome imputation, venue/date rule, minimum-observed-lane tuning, or alternative fallback is permitted in this evaluation.

This is deliberately conservative: missing lanes do not receive an inferred positive or negative Course effect.

## Fixed evaluation sample

- Race dates: **2026-07-15 through 2026-09-10 inclusive**.
- Require exactly six lanes and a valid recorded trifecta result.
- No venue exclusions, date exclusions, race-number exclusions, odds filters, or profitability filters.
- Historical result data are used only after all feature/timing eligibility is determined.
- Production PostgreSQL access is read-only.

Report samples separately:

- `ALL_ELIGIBLE`: every six-entry race with a valid BASE distribution/result.
- `COMPLETE6`: all six Course rows timing-safe.
- `MISSING1PLUS`: at least one Course row unavailable under the fixed gate.
- counts by number of usable Course lanes (0..6), date, and venue.

## Metrics

Compare fixed neutral-fallback Course probabilities against BASE on paired races:

- trifecta log loss (primary)
- Brier score (primary)
- actual-ticket probability rank (secondary)
- Top1 / Top3 / Top5 / Top10 hit rate (secondary)
- coverage / number of rescued races

Use deterministic race-level bootstrap with seed `20260911`, 5,000 resamples, reporting 95% CIs for mean delta in log loss, Brier, and rank. Negative delta is better.

## Predeclared interpretation

`SUPPORTS_NEUTRAL_FALLBACK_FORWARD_RESEARCH_ONLY` requires all of:

- `MISSING1PLUS` contains at least 200 races and at least 10 distinct dates;
- mean log-loss delta on `MISSING1PLUS` is <= 0;
- mean Brier delta on `MISSING1PLUS` is <= 0;
- mean rank delta on `MISSING1PLUS` is <= 0;
- upper bound of the 95% bootstrap CI is <= 0 for both log-loss and Brier delta;
- aggregate `ALL_ELIGIBLE` log-loss and Brier deltas are <= 0.

Otherwise status is `DO_NOT_ADVANCE_NEUTRAL_FALLBACK` or `INSUFFICIENT_MISSING_SAMPLE`.

Even a passing result does **not** authorize Production use. It only permits a separate forward-shadow review. Course 0.50, Opponent 1.0, v24/FINAL, BUY/WATCH/SKIP, LINE, thresholds, Railway config, and purchasing remain unchanged.

## Anti-leakage / no-tuning rules

- No coefficient search.
- No changing the missing-lane z=0 rule after seeing results.
- No subgroup selection to rescue a failing aggregate result.
- No use of later snapshots for a race whose morning row was absent.
- No market odds, payout, ROI, or purchase decision in this study.
- No database writes.
