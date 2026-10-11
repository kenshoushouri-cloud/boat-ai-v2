# V4 structural rank reranker preregistration — 2026-09-24

Status: `RESEARCH_ONLY / SIX_RACES_FIXED / TWO_POINTS_FIXED / FOUR_CONTEXTS_ONLY / NO_ODDS_GATE / NO_PRODUCTION_CHANGE`

## Why this experiment

The global economic rank-pair walk-forward did not improve the current `(1,2)`
control. Its main failure mode was removing rank1 too broadly.

The next question is therefore narrower:

> Can the model keep all six races and two tickets, while changing which Top5
> ranks are used only when the **pre-result ticket geometry** indicates a
> different structure?

This is deliberately not an odds-value filter and not a race-volume reduction
experiment.

## Volume invariants

Every evaluable day remains:

- the same V4 six selected races;
- exactly two tickets per race;
- 100 yen per ticket;
- no skip/no-bet;
- no replacement race.

The experiment cannot improve ROI merely by buying fewer races.

## Four fixed structural contexts

The primary policy uses only two properties already frozen in
`ranked_top5` before the result:

1. whether Top3 contains a single first-place head (`H1`) or multiple heads
   (`HM`);
2. whether Top1 and Top2 share the same first-second prefix (`P1`) or not
   (`P0`).

This creates exactly four contexts:

- `H1_P0`
- `H1_P1`
- `HM_P0`
- `HM_P1`

The immutable 2,592-race corpus has meaningful support in all four contexts
(roughly 247 to 1,060 races per context). Those counts were checked without
using outcomes or payouts.

## Why daily rank is diagnostic only

Daily rank is available in the immutable artifact, but combining it with the
four contexts would immediately create many smaller cells. To respect the
project goal of maintaining candidate volume and reducing overfit risk,
`daily_rank` is **not** used for primary selection in v1.

It may be reported descriptively after evaluation, but it cannot choose the
ticket ranks in this experiment.

## Rank-level learning

The policy does not search ten rank pairs directly.

For each context and each Top5 rank 1..5, it measures the ticket's realized
100-yen ROI in strictly earlier chronological blocks.

A prior block contributes to a context only when that block contains at least
10 races in the context. At least two qualifying earlier blocks are required.
Otherwise the context falls back to the current `(1,2)` ranks.

For block 3 onward, each rank receives a fixed score:

1. median ROI across qualifying earlier blocks;
2. cumulative ROI across those earlier context races;
3. lower rank number as deterministic tie-break.

The two highest-scoring ranks are frozen for that context for the entire next
block.

Blocks 1 and 2 are forced current control `(1,2)`.

## Result timing

The selector for a block may use only completed earlier blocks.

The evaluated block's results, payouts, hit counts and ROI cannot affect that
block's chosen ranks. After settlement, that block may become training history
for a later block.

## Explicitly excluded

The first structural experiment does not use:

- odds or EV;
- market rank;
- venue;
- race number;
- calendar month/date regime;
- daily rank for primary selection;
- model coefficient/alpha changes;
- fewer than six races;
- fewer or more than two tickets;
- stake sizing;
- LINE/purchase behavior.

## Interpretation

This is iterative historical research because the long-history corpus has
already been inspected in prior analyses. Even a positive walk-forward result
would only justify a separately frozen prospective shadow.

No Production ticket ordering change is authorized by this PR.

`FOUR_CONTEXTS / PRIOR_BLOCKS_ONLY / EXACT_SIX / EXACT_TWO_POINTS / NO_ODDS_GATE / NO_VOLUME_REDUCTION / PURCHASE_FALSE`
