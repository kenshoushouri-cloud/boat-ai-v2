# V4 formal day-strength shadow preregistration — 2026-09-27

## Purpose

Test one low-freedom future-only question:

> Do formal V4 days with stronger **pre-result selector strength** retain better realized economics than weaker formal days?

This is a shadow diagnostic only. It does not change Production, formal TOP6 selection, formal TOP2 tickets, stake, LINE, or purchase behavior.

## Why this feature

Use only `race_score`, which is already stored inside each immutable formal prospective-freeze artifact before results. No new historical feature, odds, EV, payout, or reconstructed state is introduced.

Do **not** add venue/race-number/head-p1 subgroups after seeing outcomes.

## Frozen rule

For each FORMAL_AVAILABLE day:

1. require an immutable evidence-eligible pre-result artifact;
2. require exact formal ranks 1..6 and exact 12 formal tickets;
3. compute:
   `day_strength = mean(race_score of formal daily_rank 1..6)`;
4. use the immediately prior **7 FORMAL_AVAILABLE days** only;
5. compute:
   `reference_strength = median(prior 7 day_strength values)`;
6. label:
   - `KEEP_SHADOW` when current `day_strength >= reference_strength`;
   - `SKIP_SHADOW` otherwise;
7. unavailable days are never reconstructed and do not enter the seven-day lookback.

The target-day artifact is classified before its result is read.

## Start boundary

- diagnostic target dates: **2026-09-28 JST and later**;
- 2026-09-21..09-27 artifacts may seed the input-only seven-day lookback;
- their economic outcomes must not be used to alter this rule;
- do not retrospectively score 2026-09-21..09-27 as evidence for the shadow gate.

## Review gates

First descriptive review only after all are true:

- at least 10 economically resolved future formal days from 2026-09-28 onward;
- at least 3 `KEEP_SHADOW` days;
- at least 3 `SKIP_SHADOW` days.

Report separately:
- formal TOP2 baseline on all future formal days;
- KEEP_SHADOW TOP2 ROI/profit;
- SKIP_SHADOW TOP2 ROI/profit;
- profitable-day rate;
- official/void counts;
- largest-hit share;
- whole-day bootstrap uncertainty.

A stronger KEEP result does not authorize a Production skip gate. Promotion would require a separate explicit proposal and approval.

## Forbidden

- no threshold grid;
- no changing lookback 7 after outcomes;
- no mean/median alternative search after outcomes;
- no venue/race-number/head-p1 combination search;
- no backfilling unavailable dates;
- no Production wiring/schedule/persistence in this Draft;
- no DB/result/payout/odds read in the labeler.

`FUTURE_ONLY_20260928 / ARTIFACT_NATIVE_RACE_SCORE_ONLY / PRIOR7_MEDIAN / SHADOW_ONLY / NO_RETUNE / NO_PROD_CHANGE / PURCHASE_FALSE`
