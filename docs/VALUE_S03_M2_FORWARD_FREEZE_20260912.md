# S03 Motor2 Prospective Freeze

Freeze date: 2026-09-12 JST  
Prospective start: 2026-09-13 JST

## Purpose

Freeze one timing-clean research hypothesis before future outcomes accumulate. This is a read-only Forward observation contract only. It does not change Production candidate logic, model coefficients, thresholds, LINE behavior, BUY behavior, persistence, or purchase action.

## Frozen rule: `S03_M2_POSITIVE_V1`

Source population:
- actual `v2_candidate_filter_shadow` rows with `rule_id='S03'`
- race date on or after 2026-09-13 JST

Independent Motor2 signal:
- feature: `motor_place2_rate`
- normalize the six lane values within each race to z-scores
- ticket score: `1.0*z(first) + 0.6*z(second) + 0.3*z(third)`
- frozen beta: `0.06`
- diagnostic factor: `exp(0.06 * score)`
- retained Forward observation: `score > 0.0`

The weights, beta, sign boundary, start date, source population, and flat stake accounting are frozen. They must not be retuned after 2026-09-13 outcomes are observed. Any materially different rule requires a new version/name and a new prospective start date.

## Pre-freeze evidence

Thirty-day actual PRE shadow audit through 2026-09-12:
- S03 shadow rows: 223
- Motor2-ready rows: 218
- evaluated Motor2-ready S03 rows: 186
- `M2_POSITIVE`: 101 evaluated rows retained (54.30%)
- `M2_POSITIVE`: 2 hits, flat-100-yen ROI 126.14%, profit +2,640 yen
- largest hit contributed 84.38% of returns

This is not promotion evidence. The result is fragile and month-dependent: the positive-side screen had strong August contribution but no September hit in the inspected split. The full S03 September slice was also weak (96 evaluated, 2 hits, ROI 40.94%).

## Exhibition timing decision

The 2026-08-14..2026-09-12 timing audit found:
- S03 rows: 223
- same-race exhibition rows available: 12
- exhibition captured at or before PRE snapshot: 12
- exhibition captured after PRE: 0
- exhibition minus PRE median: -203.1093 minutes

Therefore the observed exhibition rows were timing-safe, but coverage was only 12/223 (~5.38%). Exhibition is **not** part of `S03_M2_POSITIVE_V1`; adding it now would create a sparse/post-hoc rule.

## Forward review checkpoints

Review without changing the rule at 30, 50, and 100 evaluated retained observations. Report at least:
- eligible/evaluated/pending counts
- hits and hit rate
- flat 100-yen investment, return, profit, and ROI
- largest-hit share of total returns
- calendar-month breakdown

No checkpoint by itself authorizes Production promotion. Stability must be demonstrated without dependence on one month or one large payout, and all normal Value research acceptance criteria continue to apply.

## Guardrails

- read-only database access only
- no Production behavior change
- no LINE send
- no BUY action
- no model/threshold change
- no new Production persistence
- `purchase_action=false` remains unchanged
- `promotion_allowed=false` until separately reviewed and explicitly approved
