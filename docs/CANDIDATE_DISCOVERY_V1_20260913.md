# Candidate Discovery V1 — 2026-09-13

## Purpose

Build a new Boat AI candidate path with materially more opportunities than the current narrow selector, without making expected value or odds bands the primary eligibility gate.

The current v24 / S01-S05 path remains available as a reference. No Production decision logic is replaced by this research PR.

## Frozen V1 selection contract

For every race with complete six-lane race-card data:

1. Compute the v24-style 120-ticket probability distribution.
2. Select the model top-1 ticket for that race.
3. Measure three race-level structural confidence signals:
   - top-ticket probability (`p1`)
   - top-1 minus top-2 probability margin
   - probability-distribution concentration (`1 - normalized entropy`)
4. Convert each signal to a within-day percentile rank.
5. Average the three percentile ranks with equal weight.
6. Rank races for the day by that consensus score.
7. Evaluate fixed daily candidate counts of 6 / 9 / 12 / 18. The provisional primary view is **12 candidates/day**.

There is one discovery ticket per race. Odds and expected value are not used in candidate eligibility or ordering.

## Probability variants

Two frozen variants are evaluated on exactly the same contract:

- `BASE`: existing race-card model with neutral Motor2 contribution.
- `MOTOR2`: same model with the previously frozen Motor2 weight `0.06`; invalid Motor2 values fall back to `33.0`.

No coefficient search is performed in this PR.

## Existing-system relationship

S01-S05 rows from `v2_candidate_filter_shadow` are read only as a legacy reference.

The audit reports:

- race-level overlap with Discovery V1;
- exact ticket overlap;
- a recent-window union of `Discovery TOP12 + legacy S01-S05`.

This supports the migration concept: use the new system as the main research candidate source while retaining old candidates as a carryover/reference until the new system has enough Forward evidence. The legacy path can later be retired only after a separate review.

## Evaluation

Historical evaluation reads official trifecta result and payout only **after selection**. The same fixed ¥100 accounting is used for every candidate so the audit can report:

- candidate count/day;
- hit rate;
- realized ROI;
- profit/loss;
- maximum losing streak;
- month-by-month stability;
- legacy overlap.

Historical results do not alter candidate selection.

## Safety

- DB transaction is explicitly read-only.
- No `v2_odds_trifecta` query.
- No expected-value filter.
- No odds-band filter.
- No DB insert/update/delete/schema change.
- No LINE message.
- `purchase_action=false`.
- No Production selector or threshold change.
- No Railway service/Cron/config change.

This remains research-only. Any Production promotion requires a separate explicit approval after historical and prospective Forward evidence is reviewed.
