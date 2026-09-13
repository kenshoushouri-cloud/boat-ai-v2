# Candidate Discovery bet-type research contract — 2026-09-13

## Purpose

Do not assume one ticket per race is optimal. Compare multiple ticket types and multiple ticket counts from the same frozen Candidate Discovery probability distribution.

The research must separate prediction quality from purchase economics. Ticket selection rules are frozen before result evaluation to reduce retrospective overfitting.

## Common probability source

All ticket types derive from the same 120-ticket trifecta probability distribution produced by the Candidate Discovery structural model.

- Trifecta: use the 120 exact-order probabilities directly.
- Exacta: `P(a-b) = sum_c P(a-b-c)` across the four possible third-place lanes.
- Trio: `P({a,b,c})` is the sum of all six trifecta permutations for the same unordered three lanes.

This keeps the underlying race prediction identical and changes only the wagering representation.

## Frozen comparison grid

### Fixed ticket-count strategies

For each of trifecta / exacta / trio:

- TOP1
- TOP2
- TOP3
- TOP5

Stake is always **100 JPY per selected ticket**. Therefore race stake is 100 / 200 / 300 / 500 JPY respectively.

### Probability-coverage strategies

For each ticket type, select the highest-probability tickets until cumulative model probability reaches:

- 20%
- 35%
- 50%

Maximum tickets per race is capped at 12. The purpose is to compare a fixed ticket count with a confidence-dependent ticket count without using race outcome, payout, expected value, or an absolute odds band to determine the number of tickets.

## Evaluation dimensions

When only official finish order is available, compare:

- selected races
- ticket count / average tickets per race
- model probability mass covered
- race hit rate
- ticket hit rate
- losing-race streak
- monthly/day stability
- A/B/C tier behavior

When official payout data for a ticket type is available, additionally compare:

- total stake
- total return
- net profit/loss
- ROI
- maximum drawdown
- positive-month share
- return concentration in the largest one/two hits

## Current data limitation

The existing Boat AI research database and backtest paths primarily persist trifecta ticket and trifecta payout values. Official finish order can already be used to compare hit rates for derived exacta/trio selections, but exact ROI for exacta/trio requires corresponding historical payout data.

Do not approximate exacta/trio ROI using trifecta payouts.

## Mixed ticket-type strategies

Do not pre-select a mixed strategy such as "A-tier trifecta / B-tier exacta / C-tier trio" from intuition alone. First compare the frozen single-ticket-type grids above. If a mixed strategy is later proposed, freeze the mapping before its Forward sample and evaluate it separately.

## Safety

- research only
- no Production selector/model change
- no DB write/schema change
- no LINE
- no purchase action
- no Railway Production setting change

`RESEARCH_ONLY / SAME_MODEL_PROBABILITIES / 100_JPY_PER_TICKET / MULTI_POINT / TRIFECTA_EXACTA_TRIO / NO_EV_GATE / NO_ABSOLUTE_ODDS_GATE / PURCHASE_ACTION_FALSE`
