# V4 point-count marginal revenue comparison — 2026-09-23

Status: `RESEARCH_ONLY / FORMAL_1V2_EXACT / 3_TO_5_NOT_EVALUABLE_YET / NO_POST_RESULT_REGEN / NO_PRODUCTION_CHANGE`

## Question

Which fixed number of trifecta tickets per selected V4 race produces the best
incremental revenue?

The comparison must use the **same frozen pre-result ticket ranking** for every
point count. A result may be checked after the race, but ranks that were not
preserved before the deadline cannot be regenerated after results.

## Current immutable corpus

Only 2026-09-18 and 2026-09-19 are fully settled formal V4 days.

- 2 days
- 12 formal races
- 100 JPY per ticket
- immutable pre-result artifacts:
  - Sep18 artifact ID `10527500527`, JSON SHA-256
    `b195b214d8761f4efdf0c37345434ac1e96bff93815c9ecd1b00f9c87aec1a3a`
  - Sep19 artifact ID `10574052434`, JSON SHA-256
    `f2a558d0631ac830f3ffb96440b801a17fa91c98639cae8ca186585c30e46bc2`

Those artifacts preserved ranks 1 and 2 only.

## Exact current result

| Points/race | Investment | Gross return | Profit | ROI | Hit races | Hit rate | Max drawdown |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1,200 JPY | 1,190 JPY | **-10 JPY** | **99.167%** | 2/12 | 16.667% | 500 JPY |
| 2 | 2,400 JPY | 3,320 JPY | **+920 JPY** | **138.333%** | 4/12 | 33.333% | 600 JPY |
| 3 | — | — | **NOT EVALUABLE** | — | — | — | — |
| 4 | — | — | **NOT EVALUABLE** | — | — | — | — |
| 5 | — | — | **NOT EVALUABLE** | — | — | — | — |

### Marginal contribution

Point rank 1 by itself:

- incremental investment: 1,200 JPY
- gross return: 1,190 JPY
- incremental profit: **-10 JPY**
- marginal ROI: **99.167%**
- incremental exact hits: 2

Point rank 2 by itself:

- incremental investment: 1,200 JPY
- incremental gross return: 2,130 JPY
- incremental profit: **+930 JPY**
- marginal ROI: **177.500%**
- incremental exact hits: 2

Therefore the extra second point explains the entire current positive result:
`-10 + 930 = +920 JPY`.

This is descriptive evidence only. Twelve races are too few to conclude that
two points will remain optimal.

## Why 3–5 points are not filled in historically

The Sep18/Sep19 immutable artifacts do not contain ticket ranks 3, 4 or 5.

Regenerating those ranks now from historical database state would create a
result-after reconstruction path and would violate the existing Forward
evidence contract.

The evaluator therefore returns:

`NOT_EVALUABLE_MISSING_PRE_RESULT_RANKS`

for 3–5 points.

No synthetic rank, later database reconstruction or result-aware reranking is
allowed.

## Prospective 1–5 comparison design

This Draft preregisters an observation-only field:

`research_ranked_tickets`

For each already-selected formal core race, it records the top five tickets
from the **same pre-result V4 probability distribution** used to choose the
formal top two.

Important invariants:

- formal `tickets` remains exactly two;
- `CORE_TICKETS=2` remains unchanged;
- race selection/ranking remains unchanged;
- model/coefficient/threshold/stake remains unchanged;
- ranks 3–5 have no candidate-eligibility or LINE/purchase effect;
- `research_ranked_tickets[:2]` must equal the formal core tickets.

If later explicitly approved and merged, this observation allows each future
settled formal day to produce a fair cumulative 1/2/3/4/5-point comparison.

## Future decision rule

For point count `N`, track:

- total investment;
- gross return;
- net profit;
- ROI;
- exact-hit rate;
- chronological maximum drawdown;
- point-N incremental gross return;
- point-N incremental profit;
- point-N marginal ROI.

An additional point is economically useful only when its marginal return
remains attractive after its extra 100 JPY/race cost and risk.

The project should not choose a final ticket count from the current 12-race
sample. Review at the existing prospective 30/50/100-case milestones.

## Files

- evaluator:
  `research/v4_point_count_marginal_revenue.py`
- frozen current input:
  `research/evidence/v4_point_count_marginal_revenue_input_20260918_20260919.json`
- frozen current result:
  `research/evidence/v4_point_count_marginal_revenue_result_20260918_20260919.json`
- tests:
  `tests/test_v4_point_count_marginal_revenue.py`
  `tests/test_v4_point_count_rank_observation.py`

## Merge boundary

This PR is Draft research.

The evaluator/evidence itself has no Production effect.

The `research_ranked_tickets` pre-result observation would change the
Production artifact schema if merged, even though it does not change candidate
selection. Therefore **do not merge that capture change without explicit user
approval**.

## Safety

`PURCHASE_FALSE / CORE_TICKETS_2_UNCHANGED / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_SYNTHETIC_RANKS / NO_PRODUCTION_MUTATION`
