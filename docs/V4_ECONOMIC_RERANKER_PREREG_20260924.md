# V4 economic reranker preregistration — 2026-09-24

Status: `RESEARCH_ONLY / PREREGISTERED / SIX_RACES_FIXED / TWO_POINTS_FIXED / MARKET_INDEPENDENT / NO_PRODUCTION_CHANGE`

## Objective

The long-history evidence indicates that simply adding a third ticket or applying
a market-value gate does not solve the economics. The first formal ticket is the
larger long-run loss source, while the existing frozen Top5 contains enough
alternative ticket ordering to justify testing a **ticket reranker** before
reducing race volume.

The primary experiment therefore asks:

> Keeping the exact same six selected V4 races and exactly two 100-yen tickets per
> race, can an earlier-history-only economic choice among the frozen Top5 rank
> pairs outperform the current fixed rank pair (1,2)?

This experiment does **not** ask whether fewer races should be bought.

## Fixed candidate volume

The following are invariants:

- same V4 daily selector;
- exactly six selected races on every evaluable day;
- no replacement race;
- exactly two tickets per selected race;
- 100 yen per ticket;
- no skip/no-bet outcome;
- no threshold that reduces the number of races or tickets.

Therefore every evaluated policy has the same stake count as the current 6-race,
2-point control.

## Frozen ticket family

The ticket universe is the already pre-result-frozen V4 Top5.

There are exactly ten candidate rank pairs:

`(1,2), (1,3), (1,4), (1,5), (2,3), (2,4), (2,5), (3,4), (3,5), (4,5)`.

Control is always `(1,2)`.

No ticket outside Top5 may be introduced. No result-after ticket regeneration is
allowed.

## Chronological walk-forward selector

Use the same ten chronological blocks as the long-history V4 walk-forward.

- blocks 1 and 2: forced control `(1,2)` warmup;
- block 3 onward: choose one rank pair for the **entire next block** using only
  completed earlier blocks;
- the chosen pair is frozen before reading any result in the evaluated block.

The pair selection metric is fixed as:

1. highest median ROI across prior chronological blocks;
2. if tied, highest cumulative ROI across all prior races;
3. if tied, smallest distance from current control `(1,2)`;
4. if still tied, lower rank numbers lexicographically.

The primary policy is deliberately global. It does not choose separate pairs by
venue, race number, calendar month, or daily selector rank.

## Inputs allowed before result

Only information already frozen by the V4 long-history process is required:

- selected race identity;
- frozen Top5 ticket ordering;
- chronological block identity.

The primary rank-pair selector does **not** consume market prices, market ranks,
venue-specific filters, race-number filters, date subgroup filters, or result
information from the evaluated block.

## Outcome use

Historical official trifecta result and payout are used only:

1. after that race/block ticket pair is frozen;
2. to settle the already-frozen policy;
3. to become training history for strictly later blocks.

Each rank pair always stakes the same 200 yen/race, so training ROI comparisons
are economically comparable without changing candidate count.

## Required comparison

Report current `(1,2)` and the walk-forward selected-pair policy on the exact
same evaluable races:

- races and bets;
- gross return, net profit, ROI;
- hit rate;
- maximum drawdown;
- largest-hit share;
- per-block ROI;
- selected pair for each evaluated block;
- number of blocks beating control;
- paired block bootstrap for the ROI difference.

A useful result must improve economics without reducing evaluated race count or
ticket count. It is not sufficient for one large payout to explain the gain.

## Interpretation boundary

This hypothesis was designed after inspection of the existing long-history
corpus, including prior point-count and rank diagnostics. Therefore even a
positive historical walk-forward result is **iterative research evidence only**,
not pristine Production promotion evidence.

A positive result would justify a separately preregistered prospective shadow.
It would not authorize changing Production ticket ordering.

## Explicit exclusions for this first experiment

To avoid turning this into a broad parameter search, the first experiment does
not include:

- market-price or EV gates;
- venue exclusions;
- race-number exclusions;
- calendar/date regimes;
- fewer than six races;
- fewer or more than two tickets;
- daily-rank-specific rank-pair tables;
- stake sizing;
- alpha/coefficient retuning;
- automatic purchase.

`SIX_RACES_FIXED / TWO_POINTS_FIXED / TEN_PAIRS_ONLY / BLOCK_PAST_ONLY / NO_MARKET_GATE / NO_VOLUME_REDUCTION / PURCHASE_FALSE`


## Frozen historical evaluator

The first offline evaluator is now implemented as
`research/v4_economic_reranker_walkforward.py`.

It is deliberately bound to one immutable source:

- source run: `35851936772`;
- GitHub artifact: `10745234979`;
- artifact ZIP SHA-256:
  `549a4f964d087ef30b961a39c31d8d378d03eafe1f5e18eb0e7f105a96feee97`;
- `v4-long-history-walkforward.json` SHA-256:
  `4f814a4c5a89e7f014ca32a91ef9e477ce076ebd1527eeab306c96be5759b286`;
- exactly 432 evaluated days;
- exactly 2,592 evaluated races;
- exactly six races on every evaluated day;
- the ten chronological block boundaries already frozen inside that artifact.

The evaluator fails closed if the JSON hash, source contract, evaluated-day count,
evaluated-race count, exact-six structure, Top5 uniqueness, block identity, or
official result/payout fields drift.

For each block it freezes one global rank pair. Blocks 1-2 are the current
`(1,2)` control. For block 3 onward the chosen pair may use only records from
strictly earlier blocks.

The evaluator reports equal-volume control vs selected-pair economics and a
paired block bootstrap. It has no DB, Railway, network, odds, market-rank, LINE,
or purchase dependency.

The immutable artifact has **not** been evaluated in the PR workflow at this
stage. CI validates only the frozen contract and pure evaluator logic. Historical
result execution is intentionally kept as the next separate work unit.
