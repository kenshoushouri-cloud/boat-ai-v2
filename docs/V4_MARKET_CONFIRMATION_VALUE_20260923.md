# V4 market-confirmation held-out value audit — 2026-09-23

Status: `RESEARCH_ONLY / HELDOUT / TIMING_SAFE_MARKET_CONFIRMATION / NO_PRODUCTION_CHANGE`

## Why this experiment

The timing-safe V4 profit audit established two facts on the 5-minute market sample:

1. raw `model_probability × odds` gates did not produce a profitable candidate;
2. the de-vigged market predicted exact outcomes materially better than current V4 or
   the alpha0.25 shadow on this sample.

The next hypothesis is therefore **market confirmation**, not market opposition:

> only buy a V4-ranked ticket when the observable market independently confirms the
> same head or ranks the ticket inside its top ten.

## Held-out design

The same timing-safe eligible dates in 2026-08-25..2026-09-22 are split into five
chronological day blocks.

- blocks 1-2: calibration-only, excluded from reported profitability;
- blocks 3-5: held-out profitability evaluation.

No policy is selected from held-out results.

## Fixed policy family

Probability source:

- current V4;
- alpha0.25 tail blend.

Point cap:

- top 2;
- top 3.

Market confirmation gate:

- `head_agree`: model's top first-place marginal equals market's top de-vigged
  first-place marginal; keep ranked model tickets;
- `ticket_market10`: keep each ranked model ticket only when market rank <= 10;
- `head_agree_market10`: require both.

Odds floor:

- none;
- observed odds >= 3.0.

Exactly 24 policies are fixed in advance. No rank cap, odds floor or gate is changed
after held-out outcomes are observed.

## Market source

Same as PR #381 timing-safe contract:

- `v2_realtime_odds_snapshots`;
- exact coherent 120-ticket snapshot;
- maximum label spread 60 seconds;
- latest complete label fully available by deadline minus 5 minutes;
- no final/result-time odds substitution.

## Research candidate gate

A held-out policy is only flagged as a prospective hypothesis when:

- at least 30 bets;
- held-out ROI > 100%;
- both fixed held-out chronological halves ROI > 100%;
- largest hit < 50% of gross return;
- deterministic day-bootstrap P(ROI > 100%) >= 90%.

Because 24 fixed policies are compared, a pass is still only hypothesis-generation
for a separately preregistered Forward shadow.

## Safety

All confirmation decisions and ticket sets are frozen before result access.

No Production model, selector, point count, threshold, LINE or purchase behavior is
changed.

`MARKET_CONFIRMATION / HELDOUT_ONLY / FIXED_24_POLICIES / DEADLINE_MINUS_5M / RESULT_AFTER_FREEZE / PURCHASE_FALSE`
