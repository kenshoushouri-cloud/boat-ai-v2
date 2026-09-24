# V4 daily 1–3 race-count preregistration — 2026-09-24

Status: `RESEARCH_ONLY / 1_TO_3_RACES_PER_DAY / TWO_POINTS_FIXED / NO_ODDS_GATE / NO_PRODUCTION_CHANGE`

## Objective

The project no longer treats six daily purchases as a requirement.

The first low-freedom race-count experiment asks:

> If the current V4 race ordering is preserved, does buying only the top 1, 2,
> or 3 races per day improve long-run economics and the share of profitable
> days?

This experiment deliberately changes **race count only**.

## Frozen inputs

For every evaluable historical day:

- start from the same six V4 races already frozen before results;
- use `daily_race_rank` 1..6 exactly as stored;
- use the current formal two tickets: frozen Top5 ranks 1 and 2;
- stake 100 yen per ticket.

No race is regenerated and no ticket is reranked.

## Candidate policies

Three fixed daily counts are allowed:

- top 1 race/day;
- top 2 races/day;
- top 3 races/day.

Zero-race days are not part of this first experiment. More than three races are
also excluded from the adaptive policy.

The current six-race policy is retained only as the external Production control
for comparison.

## Walk-forward count selection

Use the same ten chronological blocks frozen in the immutable long-history
artifact.

- blocks 1 and 2: use 3 races/day as warmup;
- block 3 onward: select one count from {1,2,3} for the entire next block using
  only completed earlier blocks;
- current-block outcomes cannot influence current-block count.

For each candidate count, the selection score is frozen as:

1. highest median ROI across earlier chronological blocks;
2. highest median profitable-day rate across earlier blocks;
3. highest cumulative ROI over all earlier days;
4. highest cumulative profitable-day rate;
5. smaller race count as deterministic final tie-break.

The primary economic objective remains long-run ROI/profit. Profitable-day rate
is an important secondary measure, not a substitute for positive long-run
economics.

## Profitable-day definition

A day is positive only when:

`gross payout > that day's stake`.

Break-even days are not counted as profitable days.

Because every selected race retains exactly two 100-yen tickets, daily stake is:

- 1 race: 200 yen;
- 2 races: 400 yen;
- 3 races: 600 yen.

## Required report

For fixed 1R, 2R, 3R, adaptive 1–3R, and current 6R control, report:

- evaluated days;
- races and bets;
- investment, gross return, profit, ROI;
- hit rate;
- profitable-day count and profitable-day rate;
- break-even-day count;
- losing-day count;
- mean/median daily profit;
- mean profit on positive days;
- mean loss on losing days;
- maximum drawdown;
- largest-hit share;
- per-block ROI and profitable-day rate;
- adaptive race count chosen for each block;
- paired block bootstrap versus 6R control and versus the best fixed 1–3R
  baseline.

## Explicit exclusions

This first race-count experiment does not use:

- odds or EV;
- market rank;
- venue filters;
- race-number filters;
- calendar/date regimes;
- structural context filters;
- ticket reranking;
- model coefficient/alpha changes;
- stake sizing;
- result-aware same-day switching;
- LINE or purchase automation.

This is intentionally a simple test of whether **buying fewer of the already
ranked races** improves economics.

Even a positive historical result is iterative research evidence only and would
require a separately preregistered prospective shadow before any Production
change.

`TOP_1_2_3_ONLY / TWO_POINTS_FIXED / PRIOR_BLOCKS_ONLY / NO_ODDS / NO_SAME_DAY_RESULT_FEEDBACK / PURCHASE_FALSE`
