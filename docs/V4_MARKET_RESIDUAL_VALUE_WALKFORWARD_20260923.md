# V4 market-residual value walk-forward — 2026-09-23

Status: `ITERATIVE_RESEARCH / READ_ONLY_DB / MARKET_BASELINE_FIRST / HELD_OUT_VALUE_TEST / NO_PRODUCTION_CHANGE`

## Why this follows the direct EV failure

At the frozen 5-minute odds point, the direct current/alpha0.25 top-ticket EV
strategies did not approach profitability. On the same 71 timing-safe races, the
de-vigged market distribution also had substantially better multiclass LogLoss than
either V4 probability source.

The next question is therefore not "raise the V4 EV threshold". It is:

> Does alpha0.25 contain any residual information beyond the timing-safe market, and
> if so can that residual identify a small number of underpriced tickets anywhere in
> the full 120-ticket market?

This is explicitly iterative historical research. A positive result cannot be used
as Production promotion evidence.

## Frozen design

Position-conditional model training remains closed at 2026-08-09.

Profit-data period remains 2026-08-25..2026-09-22 with the existing **deadline-5m**
complete/coherent 120-ticket odds contract.

For each race:

- `m` = de-vigged inverse-odds market probability;
- `p` = frozen alpha0.25 V4 probability;
- `q_beta ∝ m^(1-beta) * p^beta`.

Fixed beta grid:

- 0.00 market only;
- 0.10;
- 0.25;
- 0.50;
- 1.00 model only.

All five distributions and all value-ticket sets are frozen before result access.

## Calibration / held-out split

Eligible dates are split into five chronological blocks.

- first two blocks: calibration only;
- beta is chosen only by lowest multiclass LogLoss, then Brier, then smaller beta;
- **profit and ROI do not choose beta**;
- chosen beta is frozen for the final three blocks;
- final three blocks are the held-out value test.

## Held-out value policy

Unlike the previous test, candidates are not restricted to the model Top2/Top3.

For all 120 tickets:

`raw_EV = q_beta(ticket) * observed_5m_odds(ticket)`

Then:

- choose at most 2 or 3 highest-EV tickets per race;
- fixed EV threshold = 1.00 / 1.05 / 1.10;
- flat 100 JPY per passing ticket;
- if no ticket passes, skip.

Market top2/top3 flat-bet results are also reported as a reference baseline.

## Research candidate gate

A held-out policy is only tagged as a future Forward hypothesis if:

- at least 30 bets;
- overall ROI > 100%;
- both chronological held-out halves ROI > 100%;
- largest single hit < 50% of gross;
- deterministic day-bootstrap P(ROI > 100%) >= 90%.

No historical result can change Production.

`MARKET_FIRST / RESIDUAL_BLEND / BETA_BY_LOGLOSS / FULL_120_VALUE_RANK / FIXED_2V3 / NO_ROI_TUNING / PURCHASE_FALSE`
