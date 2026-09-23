# V4 market-core residual value audit — 2026-09-23

Status: `ITERATIVE_RESEARCH / READ_ONLY_DB / TIMING_SAFE_5M / MARKET_CORE_ONLY / NO_PRODUCTION_CHANGE`

## Why this experiment follows the all-120 residual audit

The unrestricted market-residual experiment selected extreme residual-EV tickets
across all 120 combinations and produced zero held-out hits. Its selected blend was
also predictively worse than the de-vigged market.

The next question is narrower:

> Does alpha0.25 contain useful *ordering residual* inside the part of the market that
> already carries most outcome probability?

This avoids interpreting very large model/market disagreement on extreme longshots as
actionable value.

## Frozen rules

The same frozen alpha0.25 model trained only through 2026-08-09 is used.

Profit-test period remains 2026-08-25..2026-09-22.

Odds remain the latest coherent 120-ticket label fully captured at least 5 minutes
before deadline.

Six fixed policies are evaluated:

- market rank <= 5, best residual 2 tickets;
- market rank <= 5, best residual 3 tickets;
- market rank <= 10, best residual 2 tickets;
- market rank <= 10, best residual 3 tickets;
- market rank <= 20, best residual 2 tickets;
- market rank <= 20, best residual 3 tickets.

A ticket is eligible only when:

`alpha025_probability > de_vigged_market_probability`

Eligible tickets are ranked by:

`log(alpha025_probability / market_probability)`

No EV cutoff, odds band, venue, race-number or date subgroup is tuned.

## Interpretation

This is iterative historical hypothesis refinement after prior failures. Therefore a
positive policy can only become a separately preregistered prospective Forward shadow.

The same conservative research gate applies:

- at least 30 bets;
- overall ROI > 100%;
- both fixed chronological halves ROI > 100%;
- largest hit < 50% of gross return;
- day bootstrap P(ROI > 100%) >= 90%.

No passing result can directly alter Production.

`MARKET_CORE / POSITIVE_RESIDUAL_ONLY / TWO_OR_THREE_POINTS / RESULT_AFTER_FREEZE / FORWARD_HYPOTHESIS_ONLY / PURCHASE_FALSE`
