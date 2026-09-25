# V4 selector challenger walk-forward — 2026-09-23

Status: `RESEARCH_ONLY / READ_ONLY_DB / PRE_RESULT_SELECTOR_FREEZE / PAST_ONLY_WALKFORWARD / NO_PRODUCTION_CHANGE`

## Question

The 2025-07 onward long-history replay showed that the current daily selector has a
directional rank signal, but not enough evidence for a race-count or score-gate change.
This follow-up asks a narrower question:

> Can a simpler fixed combination of the four already-existing structural metrics
> select six races with more stable prediction accuracy than the current equal-weight
> four-metric score?

The V4 probability model, coefficients, probability temperature, formal two tickets,
and six-race daily count remain fixed.

## Preregistered selector family

The candidate family is frozen before result access and contains 15 formulas:

- each of the four metrics alone;
- all six two-metric equal-weight combinations;
- all four three-metric equal-weight combinations;
- the existing four-metric equal-weight selector as control.

Metrics are unchanged:

- `head_p1`
- `head_margin`
- `top3_mass`
- `concentration`

Each metric is percentile-ranked within that day's eligible races exactly as the
current selector does. Formula score is the equal-weight average of its included
metric ranks. Tie-breaks remain current V4: `head_p1`, then `top3_mass`, then
`race_id`.

## Timing boundary

For each date:

1. build all V4 distributions from timing-safe race-card inputs;
2. calculate structural metrics for all eligible races;
3. freeze all 15 selectors' exact six races and formal Top2 tickets;
4. only then query official result/payout rows for the union of frozen selections;
5. evaluate each selector only when its exact six results are official.

No five-race shrink, replacement, result-aware rerank, odds/EV selection, or result
access before selector freeze is allowed.

## Fair comparison

Fixed-selector comparisons use only **common-evaluable days**, where every one of the
15 selectors has six official results. This avoids comparing formulas on different
result-availability samples.

The adaptive walk-forward comparison splits common days into 10 chronological blocks:

- block 1 is warm-up only;
- before each later block, choose one selector using all prior common days only;
- primary training objective: formal Top2 exact-hit rate;
- deterministic tie-break: lower mean log loss, then selector name;
- evaluate the chosen formula on the next unseen block;
- compare against the current equal-four control on exactly the same test days.

ROI is reported as a secondary outcome, not used to choose the selector.

## Interpretation boundary

This experiment may nominate a selector for a **future prospective shadow** only.
It cannot authorize:

- Production selector changes;
- candidate-count changes;
- race-score thresholds;
- V4 coefficient / probability-temperature changes;
- ticket-count changes;
- purchase behavior.

Any prospective challenger must be preregistered separately before new Forward
results are observed.

`MODEL_FIXED / SIX_RACES_FIXED / FORMAL_2_POINTS_FIXED / SELECTOR_FAMILY_PREREGISTERED / PAST_ONLY_CHOICE / NO_RETUNE / PURCHASE_FALSE`
