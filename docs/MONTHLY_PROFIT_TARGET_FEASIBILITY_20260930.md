# Monthly +50,000 JPY target feasibility gate — 2026-09-30

Status: `RESEARCH / NO STAKE CHANGE / NO PURCHASE / NO PRODUCTION CHANGE`

## Operational goal

The project should evaluate not only ROI but also whether a clean prospective policy can support a practical monthly net-profit target of:

**+50,000 JPY / month**

This is a planning target, not a reason to retune selectors, loosen thresholds, increase candidate count, or raise stake prematurely.

## Current 100-JPY arithmetic

Assume:
- 30 operating days/month;
- 2 tickets per notified race;
- 100 JPY per ticket.

Then the monthly investment and ROI required for +50,000 JPY profit are:

| notified races/day | monthly investment | ROI required for +50,000 JPY |
|---:|---:|---:|
| 1 | 6,000 JPY | 933.33% |
| 2 | 12,000 JPY | 516.67% |
| 3 | 18,000 JPY | 377.78% |

Therefore the practical target of roughly 1-3 notified races/day cannot reach +50,000 JPY/month at a flat 100-JPY ticket stake unless ROI is extraordinarily high.

This is not a reason to increase race count or loosen thresholds. It means **edge proof and stake planning must be separated**.

## V4 formal TOP2 checkpoint

Through 2026-09-28:
- resolved formal days: 8 / 20;
- overall ROI: 147.7273%;
- second-half ROI: 135.2083%;
- leave-one-day worst remaining ROI: 112.3684%;
- formal volume: 6 races/day x 2 tickets/race;
- base stake: 100 JPY/ticket.

If 147.7273% ROI persisted for 30 days at full formal 6R/day volume:
- monthly investment: 36,000 JPY;
- projected profit: about **+17,182 JPY**.

Planning-only stake required to mathematically reach +50,000 JPY at that same volume:
- at overall ROI: about 291 JPY/ticket -> 300-JPY planning bucket;
- at second-half ROI: about 394 JPY/ticket -> 400-JPY planning bucket;
- at leave-one-day worst ROI: about 1,123 JPY/ticket -> 1,200-JPY planning bucket.

This spread is large. It shows why the project must not scale stake from the current small sample.

V4 stake-scaling review remains **blocked** until at least the existing 20-resolved-day evidence gate is satisfied and conservative economics remain >100%.

## S03_M2 checkpoint

Through 2026-09-28:
- evaluated: 63 / 100;
- overall ROI: 160.6349%;
- second-half ROI: 56.5625%;
- recent result-blind natural volume: about 2.71 races/day;
- 1 ticket per evaluated observation;
- base stake: 100 JPY.

If the current overall ROI and 2.71/day volume persisted for 30 days:
- monthly investment: about 8,130 JPY;
- projected profit: about **+4,930 JPY**.

Mathematical planning stake at the overall ROI would be about 1,014 JPY/ticket, but this is **not actionable** because:
- the 100-observation gate is not reached;
- second-half ROI is below 100%.

S03_M2 stake-scaling review is therefore blocked.

## V5/V5.1 economic sequence

The monthly +50,000 JPY target is evaluated in this order:

1. **Prove prospective edge first**
   - V4: reach the existing 20 resolved formal-day gate;
   - S03_M2: reach the existing 100 officially evaluated-observation gate;
   - do not retune to hit the profit target.

2. **Measure natural usable volume**
   - target context remains roughly 1-3 high-quality notified races/day;
   - zero days are acceptable when quality is absent.

3. **Use conservative economics for scaling review**
   - overall ROI alone is insufficient;
   - chronological later-half, leave-one-day/hit sensitivity, drawdown and losing streak matter.

4. **Only then review stake separately**
   - any Production stake change requires its own approval;
   - bankroll / maximum drawdown limits must be defined first;
   - purchase remains disabled until separately approved.

## Guardrail

`MONTHLY_PLUS_50000_IS_A_SCALING_OBJECTIVE_NOT_A_SELECTOR_TUNING_OBJECTIVE / PROVE_EDGE_FIRST / NO_THRESHOLD_RELAXATION / NO_STAKE_CHANGE_YET / PURCHASE_FALSE`
