# Candidate Discovery — Multi-Bet ROI Acceptance Contract (2026-09-13)

This contract is frozen before the first 30-day official-K payout smoke result is interpreted.

## Purpose

Prevent post-outcome strategy selection while comparing 3連単 / 2連単 / 3連複 and multiple point-count patterns.

## Frozen comparison grid

- race selector: Candidate Discovery V2 structural ranking, `MOTOR2_FACTOR`
- daily race cap: 6
- tier map: A=rank 1-2 / B=3-4 / C=5-6
- bet types: trifecta / exacta / trio
- fixed ticket counts: TOP1 / TOP2 / TOP3 / TOP5
- probability coverage: 20% / 35% / 50%, max 12 tickets
- stake: 100 JPY per selected ticket
- candidate selection does not use payout, odds, or EV

## First payout smoke

Fixed period: `2026-08-14..2026-09-12`.

The 30-day smoke is used to validate the official-K payout parser and establish preliminary economics only. It cannot authorize Production promotion or a final purchase recipe.

## Interpretation rules

1. Do not select the highest 30-day ROI strategy as the final strategy.
2. Do not change point counts, coverage targets, race cap, tier definitions, or bet-type derivation after seeing the smoke result.
3. Report every predeclared strategy, including poor results.
4. For any apparently profitable strategy, inspect at minimum:
   - realized ROI and profit;
   - race hit rate;
   - maximum losing-race streak;
   - maximum drawdown;
   - positive-day rate;
   - largest single-hit share of total returns;
   - A/B/C tier behavior;
   - missing official payout coverage.
5. A strategy with ROI >100% in the smoke remains research-only, especially if dominated by one large payout or a small number of positive days.
6. If the payout parser is healthy, the next formal comparison must reuse this same frozen grid on a materially longer historical period or fixed chronological chunks. No smoke-driven parameter tuning is allowed before that comparison.
7. Mixed A/B/C bet-type recipes may be proposed only after the fixed-grid profitability comparison. Any such recipe must then be frozen prospectively before Forward results.
8. Existing 2026-09-13 Candidate Discovery Forward freeze must never be retroactively rewritten to match a later winning ticket type or point count.

## Safety

- Research only
- DB read only
- no schema change
- no LINE send
- no purchase action
- no Production selector change
- no Railway Production config change

`SMOKE_ONLY / SAME_GRID / 100_YEN_PER_TICKET / NO_POSTHOC_TUNING / PURCHASE_ACTION_FALSE / NO_PRODUCTION_CHANGE`
