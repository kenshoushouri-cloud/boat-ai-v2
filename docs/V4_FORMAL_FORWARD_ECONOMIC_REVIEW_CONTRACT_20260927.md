# V4 formal Forward economic review contract — 2026-09-27

Frozen after read-only inventory of the formal prospective evidence stream.

## Evidence universe

Formal prospective period begins with the arbiter contract frozen before the 2026-09-16 primary.

The provider-wide read-only inventory scanned 60 workflow runs and found 10 formal artifact copies. Applying the already-frozen arbitration rule to every date 2026-09-16..2026-09-27 produced:

- 2026-09-16: UNAVAILABLE_NO_VALID_CAPTURE
- 2026-09-17: UNAVAILABLE_NO_VALID_CAPTURE
- 2026-09-18: UNAVAILABLE_NO_VALID_CAPTURE
- 2026-09-19: UNAVAILABLE_NO_VALID_CAPTURE
- 2026-09-20: UNAVAILABLE_NO_VALID_CAPTURE
- 2026-09-21: FORMAL_AVAILABLE
- 2026-09-22: FORMAL_AVAILABLE
- 2026-09-23: FORMAL_AVAILABLE
- 2026-09-24: FORMAL_AVAILABLE
- 2026-09-25: FORMAL_AVAILABLE
- 2026-09-26: FORMAL_AVAILABLE
- 2026-09-27: FORMAL_AVAILABLE, results not yet present at the 2026-09-27 audit

Unavailable dates stay unavailable. They must never be reconstructed from historical database state.

When more than one valid capture exists on a date, the existing frozen arbiter remains authoritative: earliest valid generated timestamp, same-time/same-core duplicates collapsed, same-time/different-core fail closed, later valid captures diagnostic only.

## Economic settlement

Only the exact immutable 6-race / 12-ticket formal core is settled.

- TOP1 view: core_order=1 only, 100 JPY per official race.
- Formal TOP2 view: core_order=1 and 2, 100 JPY each per official race.
- Cancelled races are void/refund and contribute zero investment and zero return.
- Missing/unresolved results remain pending and do not create a loss.
- No odds are read.
- No candidate is regenerated.
- Results and payouts are read only after the artifact set is validated and frozen.

## Current complete-day checkpoint

Through 2026-09-26 there are six economically resolved formal days.

Formal TOP2:
- official races: 32
- void races: 4
- bets: 64
- exact hits: 10
- investment: 6,400 JPY
- return: 10,970 JPY
- profit: +4,570 JPY
- ROI: 171.4062%
- profitable days: 3 / 6
- first three formal days ROI: 191.0714%
- second three formal days ROI: 156.1111%
- largest single payout: 3,590 JPY
- largest-hit share: 32.7256%
- leave-one-hit-out minimum ROI: 119.0323%
- leave-one-day-out worst remaining ROI: 125.1923%
- whole-day bootstrap, 20,000 samples:
  - median ROI 171.4062%
  - 95% interval [58.0%, 281.1765%]
  - P(ROI > 100%) 89.13%

TOP1 is not profitable at this checkpoint:
- investment 3,200 JPY
- return 2,570 JPY
- profit -630 JPY
- ROI 80.3125%

Predicted-head accuracy is computed only on official-result races; void races are excluded from its denominator. The corrected checkpoint uses 32 official races.

## Frozen future review

Do not change core race count, TOP2 point count, selector, coefficients or stake from this small checkpoint.

Review the unchanged formal TOP2 stream at:
- 10 economically resolved formal days;
- 20 economically resolved formal days;
- 30 economically resolved formal days.

At every checkpoint report:
- formal available / unavailable dates;
- official / void / pending races;
- TOP1 and TOP2 ROI/profit;
- profitable-day rate;
- chronological halves;
- largest-hit share;
- leave-one-hit and leave-one-day sensitivity;
- whole-day bootstrap uncertainty;
- any formal artifact ambiguity.

A positive checkpoint is manual-review evidence only. It does not authorize Production changes or automatic purchase.

`IMMUTABLE_ARTIFACT_ONLY / FROZEN_ARBITER / UNAVAILABLE_DAYS_STAY_UNAVAILABLE / CANCELLED_REFUND / TOP2_UNCHANGED / NO_RETUNE / NO_AUTOPROMOTION / PURCHASE_FALSE`
