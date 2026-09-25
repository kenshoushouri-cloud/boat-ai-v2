# Value Candidate Shadow Research Contract

Date: 2026-09-12 JST
Status: research-only / default-off / no Production behavior change

## Goal

Keep the current v24 Production BUY/WATCH/SKIP path unchanged while testing a second, independent candidate-generation method that can increase opportunity count without relaxing the existing selector.

The research question is not "how to force more BUY decisions". It is:

> Can already-collected race, entry, motor, exhibition, weather, course/opponent and odds data identify additional positive-value tickets at small stake sizes while preserving a long-run positive ROI?

## Core method

For each ticket with a calibrated model probability `p` and contemporaneous decimal odds `o`, compute:

- break-even probability: `1 / o`
- value ratio: `p * o`
- edge: `p - (1 / o)`

A low-odds ticket is not excluded merely because the odds are below the current Production range. Likewise, a high-odds ticket is not accepted merely because the payout is large.

This research must evaluate odds bands separately, including at minimum:

- 1.5-2.0
- 2.0-3.0
- 3.0-5.5
- 5.5-10.0
- 10.0-20.0
- 20.0+

For each band report candidate count, hit rate, turnover, payout, ROI, expected value calibration, monthly profit/loss and longest losing streak.

## Strict separation from Production

The current Production selector remains the control arm and is not modified.

The alternative path is shadow-only and must not:

- change `MIN_ODDS`, `MAX_ODDS`, selector modes, model coefficients or Production thresholds;
- change Racer Course coefficient 0.50 or Opponent Pressure coefficient 1.0;
- save Production Forward decisions;
- send LINE messages;
- trigger purchase actions;
- create or alter Production schema;
- write research rows into the Production database.

`purchase_action=false` remains mandatory.

## Storage budget

Railway Production storage is constrained. At the start of this research the database disk is already about 4.18 GB on a 5 GB volume, so this experiment is deliberately designed to add effectively zero persistent Production storage.

Allowed:

1. read existing tables in a read-only transaction;
2. stream rows in bounded date/race batches;
3. aggregate in process memory;
4. emit compact JSON/CSV summaries to CI artifacts or console logs;
5. commit only small code/tests/docs to GitHub.

Not allowed without a separate approval:

- a new always-on shadow table;
- ticket-by-ticket persistent shadow rows;
- duplicating odds snapshots;
- a new Railway database/service/volume;
- a new Production Cron;
- historical backfill writes.

Target output size for a full backtest summary should be measured in KB/low MB, not GB.

## Candidate-generation phases

### Phase A — odds-band opportunity audit

Use the existing scoring/probability outputs where historically reproducible and remove only the research-time fixed 3.0-5.5 odds exclusion. Measure whether potentially profitable observations exist below 3.0 and above 5.5.

No new model is claimed at this phase.

### Phase B — calibrated value gate

For each eligible ticket calculate value ratio and edge. Test predeclared value gates such as 1.02, 1.05, 1.10, 1.15 and 1.20. Results must be segmented by odds band, venue and calendar month.

Threshold selection must use train/validation separation and must not be promoted from in-sample ROI alone.

### Phase C — data-ablation / incremental value

Compare the base estimate with additional information layers one at a time:

- Racer Course
- Opponent Pressure
- motor/boat
- exhibition/ST
- weather/wind/wave
- venue/course context
- odds movement when timing-safe historical snapshots exist

The purpose is to determine which data layers add out-of-sample calibration/value, not merely fit historical winners.

### Phase D — small-stake portfolio simulation

Simulate fixed small stakes first, before any Kelly-style sizing. Suggested research stake grid:

- 100 yen/ticket
- 300 yen/race cap
- 500 yen/race cap
- 1,000 yen/race cap
- 2,000 yen/race cap

Report monthly turnover and profit. A method that requires 10,000 yen per race to meet the profit goal is not considered suitable for this project.

## Business target

The user target is monthly profit in the tens of thousands of yen without high stake per race. Therefore the analysis must jointly optimize:

- positive out-of-sample ROI;
- sufficient candidate frequency;
- bounded drawdown/losing streak;
- small per-race stake;
- operational/storage cost.

A useful result is not necessarily a single strategy. A portfolio of several independently validated low-stake value segments may be preferable to forcing the existing high-selectivity Production strategy to produce more candidates.

## Go / No-Go evidence

Do not recommend Production promotion unless an out-of-sample/forward shadow period shows all of:

1. positive ROI after realistic payout/stake accounting;
2. materially higher candidate frequency than the current Production selector;
3. no dependence on result leakage or post-deadline data;
4. acceptable monthly drawdown under the small-stake caps;
5. stable enough performance across multiple months/venues to avoid one-period overfit;
6. storage impact remains negligible.

Until then, this is a research comparison only.
