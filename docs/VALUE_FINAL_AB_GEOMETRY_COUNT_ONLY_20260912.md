# `final_ab` Candidate Geometry — Count Only

Freeze date: 2026-09-12 JST

## Purpose

Map where candidate density currently exists in the Production `final_ab` market without using race results, payouts, hit flags, ROI, or any other outcome signal. The purpose is to choose future research hypotheses by operational volume and economic interpretation rather than by mining realized profit.

This audit is deliberately outcome-blind. It must not query `v2_results` or Candidate Shadow settlement fields.

## Source integrity

Period: 2026-08-25 through 2026-09-12.

A race is included only when its `final_ab` realtime odds snapshot is:

- exactly 120 rows
- exactly 120 distinct tickets
- all odds > 1.0
- timestamp spread <= 60 seconds
- fully captured no later than `deadline_at`
- six race-entry lanes available

The ranking function is the existing `v24_pre_candidate_notifier_pg._rank_candidates` and is not modified.

## Fixed bins

Probability-rank bands:

- 1–5
- 6–10
- 11–20
- 21–40
- 41–80
- 81–120

Market-rank bands use the same boundaries. Odds bands are:

- `<3`
- `3–6`
- `6–10`
- `10–20`
- `20–30`
- `30–50`
- `50+`

Race groups are 1–3R, 4–6R, 7–9R, and 10–12R.

## Fixed disagreement families

Rank is better when numerically smaller.

- `MODEL_AHEAD_20P`: `market_rank - prob_rank >= 20`
- `MODEL_AHEAD_10P`: `10 <= market_rank - prob_rank < 20`
- `MODEL_AHEAD_5P`: `5 <= market_rank - prob_rank < 10`
- `ALIGNED_4P`: `abs(market_rank - prob_rank) <= 4`
- `MARKET_AHEAD_5P`: `5 <= prob_rank - market_rank < 10`
- `MARKET_AHEAD_10P`: `10 <= prob_rank - market_rank < 20`
- `MARKET_AHEAD_20P`: `prob_rank - market_rank >= 20`

These labels are descriptive only. They are not profitability claims.

## Outputs

The audit reports:

- source coverage and minutes-to-deadline distribution
- ticket count and distinct-race count for fixed rank × odds cells
- distinct-race count for fixed disagreement family × odds band × race group
- 30-calendar-day-equivalent race count for each family slice

No result or payout table is read. No ROI is calculated. No cell is promoted automatically.

A later prospective rule may be frozen only after reviewing count density and economic meaning. Its future outcomes must start after the freeze date; historical outcomes must not be used to select the rule.

## Guardrails

- read-only DB transaction
- no `v2_results` query
- no Candidate Shadow hit/return fields
- no DB write
- no Production behavior change
- no model/threshold change
- no Railway/Cron/service change
- no LINE send
- no BUY action
- `promotion_allowed=false`
