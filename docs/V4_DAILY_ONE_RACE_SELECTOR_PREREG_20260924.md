# V4 daily one-race selector preregistration — 2026-09-24

Status: `RESEARCH_ONLY / EXACTLY_ONE_RACE_PER_DAY / TWO_POINTS_FIXED / FOUR_CONTEXTS_ONLY / NO_ODDS / NO_PRODUCTION_CHANGE`

## Objective

The 1–3 race-count study showed that reducing daily purchase volume sharply
reduces loss magnitude and drawdown, but simply taking frozen daily rank 1 is not
enough to establish positive out-of-sample economics.

The next low-freedom question is:

> Keeping exactly one purchase race per evaluable day, can the six already
> frozen V4 candidates be reordered economically using only broad pre-result
> ticket structure learned from earlier chronological blocks?

This experiment changes **which one race is selected**, not how many tickets are
bought in that race.

## Fixed daily volume

Every evaluable day has:

- the same six V4 candidate races;
- exactly one selected race;
- exactly two frozen formal tickets in that race;
- 100 yen per ticket;
- exactly 200 yen daily stake.

There is no no-bet day in this experiment.

## Four broad structural contexts

Only two properties of the already-frozen Top5 are used:

1. whether Top3 uses one first-place head (`H1`) or multiple heads (`HM`);
2. whether Top1 and Top2 share the same first-second prefix (`P1`) or not
   (`P0`).

The four fixed contexts are:

- `H1_P0`
- `H1_P1`
- `HM_P0`
- `HM_P1`

Outcome-free support in the immutable 2,592-race source is:

- `HM_P0`: 1,060 races;
- `H1_P1`: 665 races;
- `H1_P0`: 620 races;
- `HM_P1`: 247 races.

No context was chosen because of its historical payout result.

## Walk-forward economic score

Blocks 1 and 2 use the current daily-rank-1 race.

For block 3 onward, each context may use only strictly earlier blocks. A prior
block contributes only if it contains at least 10 races of that context, and a
context needs at least two qualifying prior blocks.

For each eligible context, freeze:

1. median formal-two-ticket ROI across qualifying prior blocks;
2. cumulative formal-two-ticket ROI over those qualifying prior races.

These two values rank contexts for the entire next block.

For each day in that block:

- score all six races by their frozen structural context;
- choose the race from the highest-scoring eligible context;
- if multiple races share the same context score, use higher already-frozen
  `race_score`;
- then lower `daily_race_rank`;
- then deterministic race ID;
- if no context has sufficient prior evidence, fail closed to daily rank 1.

The current day's payout/result is never visible to this choice.

## Why race_score is only a tie-break

The existing V4 race_score already determines the current daily ranking. This
experiment does not refit or tune its coefficients.

Using race_score only after the broad context economic score avoids creating a
new continuous threshold search while still preferring the stronger current V4
candidate when two races have the same learned context.

## Required evaluation

Compare, on the exact same evaluable days:

- fixed daily-rank-1 / 1R-per-day baseline;
- the new exactly-one-race selector;
- current 6R Production control as an external reference.

Report:

- days, races, bets and investment;
- gross return, profit and ROI;
- hit rate;
- profitable/break-even/losing day counts;
- profitable-day rate;
- mean and median daily profit;
- mean positive-day profit and mean losing-day loss;
- maximum drawdown;
- largest-hit share;
- selected daily-rank distribution;
- selected structural-context distribution;
- per-block ROI;
- blocks beating the fixed 1R baseline;
- paired block bootstrap versus fixed 1R.

## Explicit exclusions

This first one-race selector does not use:

- odds or EV;
- market rank;
- venue;
- race number;
- calendar/date regime;
- daily-rank-specific economic tables;
- 24-cell context-by-rank tables;
- ticket reranking;
- model alpha/coefficient tuning;
- zero-race days;
- more than one race/day;
- same-day result feedback;
- stake sizing;
- LINE or automatic purchase.

This is iterative historical research. A positive result would require a
separately preregistered prospective shadow before any Production change.

`EXACTLY_ONE_RACE / EXACT_TWO_TICKETS / FOUR_CONTEXTS / PRIOR_BLOCKS_ONLY / RACE_SCORE_TIEBREAK_ONLY / NO_ODDS / PURCHASE_FALSE`
