# V4 structural conditional reranker preregistration — 2026-09-24

Status: `RESEARCH_ONLY / PREREGISTERED / SIX_RACES_FIXED / TWO_POINTS_FIXED / NO_ODDS_GATE / NO_PRODUCTION_CHANGE`

## Why this experiment exists

The first global economic reranker kept candidate volume fixed but performed worse
than the current rank pair `(1,2)`. That result is useful: rank1 is economically
weak in aggregate, but removing it globally sacrifices too much hit probability.

The next question is narrower:

> Can rank1 be replaced only in structural situations where earlier chronological
> blocks consistently support the replacement, while keeping rank2 and preserving
> all six races and both tickets?

This is a new hypothesis formed after inspection of the existing long-history
corpus, so any historical result remains iterative research evidence only.

## Volume invariants

Every evaluable day remains:

- exactly six current V4 selected races;
- exactly two tickets per race;
- exactly 100 yen per ticket;
- no skipped race;
- no replacement race;
- no stake sizing.

The experiment cannot improve ROI by shrinking candidate volume.

## Frozen structural state

Only fields already frozen before result in the immutable long-history artifact
are allowed.

The state space is deliberately small: six states total.

### Daily selector rank bucket

- `high`: daily rank 1-2
- `mid`: daily rank 3-4
- `low`: daily rank 5-6

### Top5 head structure

- `single_head`: all five frozen Top5 tickets have the same first-place lane;
- `multi_head`: the frozen Top5 contains at least two different first-place lanes.

No venue, race number, calendar month/date, odds, market rank, or reconstructed
probability metric is part of this first conditional experiment.

The source artifact contains `race_score`, but it is intentionally not added as
another split variable in v1 to avoid widening the search space.

## Frozen ticket family

Rank2 is always retained because previous long-history decomposition showed that
rank2 was economically stronger than rank1.

The only permitted pairs are:

- control: `(1,2)`;
- replace rank1 with rank3: `(2,3)`;
- replace rank1 with rank4: `(2,4)`;
- replace rank1 with rank5: `(2,5)`.

No other Top5 combination is evaluated in the primary v1 hypothesis.

## Chronological selection

Use the same ten chronological blocks frozen in the immutable long-history
artifact.

- blocks 1-2 are forced control;
- block 3 onward computes one pair per structural state;
- only races from strictly earlier blocks in the same structural state may train
  that state;
- fewer than 40 prior races in a state => fail closed to control;
- fewer than two prior chronological blocks in a state => fail closed to control.

An alternative pair may replace control only if, within that state, it beats
control on **both**:

1. median ROI across earlier chronological blocks;
2. cumulative ROI across all earlier races.

Otherwise the state remains `(1,2)`.

If multiple alternatives pass, choose highest prior-block median ROI, then
highest cumulative ROI, then the lower replacement rank as deterministic
conservative tie-break.

## Immutable source for the later evaluator

The future evaluator must bind to the same long-history evidence:

- run: `35851936772`;
- artifact: `10745234979`;
- artifact ZIP SHA-256:
  `549a4f964d087ef30b961a39c31d8d378d03eafe1f5e18eb0e7f105a96feee97`;
- JSON SHA-256:
  `4f814a4c5a89e7f014ca32a91ef9e477ce076ebd1527eeab306c96be5759b286`;
- 432 exact-six evaluated days;
- 2,592 races.

The evaluation has **not** been run under this contract yet.

## Required reporting

Compare conditional reranker vs current `(1,2)` on the exact same races and
investment:

- ROI and net profit;
- hit rate;
- maximum drawdown;
- largest-hit share;
- per-block ROI;
- pair chosen for each of the six states in every block;
- switch frequency from control;
- block wins/ties/losses;
- paired block bootstrap of ROI difference.

## Exclusions

This preregistration explicitly excludes:

- odds/EV gating;
- candidate reduction;
- venue filtering;
- race-number filtering;
- month/date filtering;
- `race_score` thresholding;
- reconstructed `head_p1`, `head_margin`, `top3_mass`, or
  `concentration` not already preserved in the immutable result record;
- changing the daily six-race selector;
- changing point count or stake;
- Production changes;
- automatic purchase.

`SIX_RACES_FIXED / TWO_POINTS_FIXED / RANK2_ANCHOR / SIX_STRUCTURAL_STATES / PAST_BLOCKS_ONLY / NO_ODDS / PURCHASE_FALSE`
