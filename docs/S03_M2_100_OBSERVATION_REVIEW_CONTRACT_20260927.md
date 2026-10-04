# S03_M2_POSITIVE_V1 — 100-observation review contract

Frozen on: 2026-09-27 JST  
Applies to the already-frozen prospective rule `S03_M2_POSITIVE_V1`.

## Evidence boundary

Only rows satisfying all of the following may enter the 100-observation review:

- race date on or after 2026-09-13 JST;
- original stored `S03` shadow row;
- stored `snapshot_at < deadline_at`;
- complete six-lane `motor_place2_rate`;
- exact frozen Motor2 score:
  `1.0*z(first) + 0.6*z(second) + 0.3*z(third)`;
- frozen beta `0.06`;
- frozen retain rule `score > 0.0`;
- flat 100 JPY per retained observation;
- no reconstructed or backfilled candidate row.

The historical pre-freeze ROI is not promotion evidence. The 2026-09-27 timing reconciliation showed that the old pre-freeze profitable result depended materially on late/invalid stored rows.

## Mandatory 100-observation report

When 100 timing-valid retained observations are evaluated, report without changing the rule:

1. evaluated / pending / timing-rejected / missing-Motor counts;
2. hits, investment, return, profit and ROI;
3. largest hit and largest-hit share of gross return;
4. maximum drawdown and maximum losing streak;
5. calendar-month breakdown;
6. chronological first-half versus second-half ROI using the 100 observations in time order;
7. whole-day bootstrap, 20,000 samples, fixed seed `20260927`:
   - median ROI;
   - 95% interval;
   - P(ROI > 100%);
8. candidate frequency per calendar month;
9. confirmation that the source rule, score weights, beta, sign boundary and stake never changed.

## Interpretation

The 100-observation checkpoint is a **manual review gate**, not automatic promotion.

Fail closed if:
- timing integrity is violated;
- the frozen rule changed;
- reconstructed/backfilled observations are required;
- ROI is not above 100% at the frozen 100-observation checkpoint.

If ROI remains above 100%, review stability jointly:
- first and second chronological halves;
- month-to-month behavior;
- largest-hit concentration;
- drawdown / losing streak;
- whole-day bootstrap uncertainty.

A positive review may justify a separate Production proposal only. It does not itself authorize any Production model, candidate, threshold, stake, LINE, Railway, DB-write or purchase change.

## Current checkpoint context — not a new threshold

At 53 timing-valid **officially evaluated** observations through 2026-09-27:
- ROI 190.9434%;
- profit +4,820 JPY;
- largest-hit share 44.3676%;
- max drawdown 1,600 JPY;
- max losing streak 16;
- whole-day bootstrap P(ROI > 100%) 86.13%;
- first chronological half ROI 319.6154%;
- second chronological half ROI 67.0370%.

One Motor2-positive row had `evaluation_status=invalid_result` and is excluded from investment/ROI. Invalid/cancelled results must never be counted as a 100 JPY losing bet.

These numbers are recorded only as the current checkpoint. They must not be used to alter the frozen rule or invent a new subgroup before the 100-observation review.

`FROZEN_RULE / STRICT_PREDEADLINE_ONLY / 100_OBSERVATION_MANUAL_REVIEW / NO_RETUNE / NO_AUTOPROMOTION / PURCHASE_FALSE`
