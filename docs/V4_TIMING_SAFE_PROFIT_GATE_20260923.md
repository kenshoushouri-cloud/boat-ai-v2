# V4 timing-safe profit gate — 2026-09-23

Status: `RESEARCH_ONLY / READ_ONLY_DB / PREDEADLINE_ODDS / FIXED_POLICY_GRID / NO_PRODUCTION_CHANGE`

## Objective

The current V4 research has narrowed the model question to a practical economics
question:

> Can the current two-point or shadow three-point ticket ranking become profitable
> if we **skip bets whose pre-deadline market odds do not justify the model
> probability**?

This study does not change the six-race selector, model coefficients or Production
ticket count.

## Strict train/test split

The position-conditional tail model is trained only on historical blocks ending
**2026-08-09**.

The profit test is **2026-08-25 through 2026-09-22**.

No test-period result updates the model.

Two probability sources are evaluated:

- `current`: current V4 distribution;
- `alpha025`: current V4 blended 25% with the position-conditional tail model
  frozen before the profit-test period.

## Timing-safe odds

Odds source: `v2_realtime_odds_snapshots`.

For each already-selected V4 race, use only the latest snapshot label satisfying:

- exactly 120 rows;
- exactly 120 valid distinct trifecta tickets;
- every odd > 1.0;
- label timestamp spread <= 60 seconds;
- final ticket timestamp <= race deadline minus **5 minutes**.

If no such snapshot exists, the race is not evaluated for the value policy. It is
never replaced with another race and final/result-time odds are never substituted.

## Fixed policy grid

No threshold is learned from the test outcomes.

For each probability source:

- point cap: 2 or 3 ranked tickets;
- raw EV gate: no gate, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25;
- raw EV = frozen model probability × observed timing-safe odds;
- flat stake 100 yen for each ticket that passes;
- if no ticket passes, skip the race.

This gives 28 fixed policies.

## Market-residual diagnostic

On the same timing-safe settled races, report exact-ticket:

- de-vigged inverse-odds market LogLoss and Brier;
- current V4 LogLoss/Brier;
- alpha0.25 LogLoss/Brier.

This determines whether model probability contains useful information relative to
the market before interpreting EV output.

## Historical profit-candidate gate

A fixed policy is tagged only as a **research Forward hypothesis** when all hold:

- at least 30 bets;
- overall realized ROI > 100%;
- both pre-fixed chronological halves have ROI > 100%;
- largest single hit contributes < 50% of total gross return;
- deterministic day-bootstrap P(ROI > 100%) >= 90%.

Passing this gate does **not** authorize Production. Multiple fixed policies are
tested, so any historical positive result still requires a separately
preregistered prospective Forward shadow.

## Safety

- all distributions, odds snapshots and policy ticket sets freeze before result read;
- DB transaction is READ ONLY;
- no Production write/persistence;
- no threshold/model/selector/ticket-count mutation;
- no LINE;
- no purchase;
- `purchase_action=false`.

`FIXED_2V3 / FIXED_EV_GRID / DEADLINE_MINUS_5M / RESULT_AFTER_FREEZE / NO_POST_HOC_THRESHOLD / FORWARD_HYPOTHESIS_ONLY`


## Cutoff correction before economic interpretation

The initial execution used a 15-minute cutoff and produced zero evaluable V4 races.
A separate result-free coverage ladder then showed, for the exact 174 selected V4
races in the test period:

- any realtime odds rows: 174 / 174;
- coherent complete 120-ticket label: 127 / 174;
- complete by deadline: 121 / 174;
- complete by deadline-5m: 71 / 174;
- complete by deadline-10m: 18 / 174;
- complete by deadline-15m: 0 / 174.

This does **not** justify choosing 5 minutes from profitability. No profitability
was observable in the 15-minute run.

The 5-minute cutoff is instead anchored to the pre-existing Production operating
contract documented on main before this research:

- `docs/DEVELOPMENT_STATUS.md`: FINAL market-late window = **0–7 minutes before deadline**;
- `docs/OPS_STATUS_2026-08-24.md`: market-late = **0–7 minutes**, including an
  exact-120 live capture at 5.46 minutes before deadline;
- current FINAL collector code accepts races inside its configured pre-deadline
  window and rejects only passed deadlines.

Five minutes is therefore a fixed, operationally feasible point inside the existing
late-market decision window while retaining a nonzero manual-action buffer. It is
not to be moved again in response to ROI.
