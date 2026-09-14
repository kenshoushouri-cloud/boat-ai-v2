# Candidate Purchase Policy Evaluation Plan — 2026-09-14

Status: **RESEARCH ONLY / PRE-RESULT PREREGISTRATION / NO PRODUCTION CHANGE**

## Purpose

Candidate Discovery V4 is intentionally broader than the old Production selector. The research goal is to avoid returning to a system that is so restrictive that usable days routinely show no candidates, while also avoiding the opposite failure mode of forcing all 12 Stage-1 tickets into purchases.

This document freezes the evaluation boundary **before the first scheduled daily V4 prospective freeze on 2026-09-15**.

It does not create a Production BUY rule, does not change V4 ranking, does not change Stage-2 market corroboration, and does not authorize any purchase or stake change.

## Fixed separation: candidate feed vs purchase decision

Stage 1 remains the fixed research candidate feed:

- 6 races/day
- 2 exact-order trifecta tickets/race
- 12 core candidate tickets/day on a complete, eligible day
- Course coefficient 0.50
- Opponent Pressure coefficient 1.0, first-place only
- Motor2 beta 0.06 with position weights 1.0 / 0.6 / 0.3
- 4 structural metrics equal-weight daily race ranking
- no Stage-1 EV gate
- no absolute odds eligibility gate
- `purchase_action=false`

The 12 tickets are **not a purchase quota**.

The candidate feed should remain broad enough to preserve ranking information. A later purchase layer may select fewer tickets, or zero tickets when evidence is insufficient. A source-incomplete or timing-invalid day remains fail-closed even if that creates no valid feed.

## User objective

Operational preference:

- avoid old-system-style chronic zero-candidate output on otherwise eligible complete-data days;
- do not force 12 purchases/day;
- do not chase a fixed daily profit;
- basic monthly evaluation reference: +30,000 JPY;
- stretch monthly evaluation target: **+50,000 JPY**.

The profit figures are evaluation targets, **not selector thresholds**. They must never be used as a reason to relax a rule after seeing outcomes, increase stake to recover a daily loss, or keep buying until a daily target is reached.

## Prospective evidence only

A date may enter V4 purchase-policy evaluation only if its original V4 freeze is timestamp-proven prospective evidence and passes the existing V4 guard, including:

- actual current JST date;
- generation after the fixed 08:15 JST source cutoff;
- complete scheduled/evaluable race universe;
- exactly 6 core races / 12 core tickets;
- all frozen rows before the earliest feed deadline;
- `prospective_evidence_eligible=true`;
- `purchase_action=false`.

2026-09-14 is excluded because the V4 prospective freeze was missed. It must never be reconstructed after outcomes.

The 2026-09-13 immutable artifact remains BASELINE-only and must not be mixed into V4 purchase-policy performance.

## Frozen Stage-2 hypothesis

Stage 2 remains:

`MKT_LATE07_TOP2_SUPPORT_V1`

Definition already frozen elsewhere:

- timing-safe market observation 0..7 minutes before deadline;
- TOP2 market support;
- Stage 1 candidates are not removed or reranked by Stage 2;
- supported-case milestones 30 / 50 / 100;
- no post-outcome retuning.

This plan does not invent a new odds threshold or market cutoff.

## What to measure every eligible day

Candidate availability and purchase-opportunity reporting must remain separate.

Candidate-feed metrics:

- eligible complete-data days;
- successful V4 freeze days;
- core races/day;
- core tickets/day;
- fail-closed days and exact reason;
- candidate-feed availability rate.

Potential-purchase metrics, still research-only:

- Stage-2 supported cases;
- supported tickets/day;
- zero-supported-ticket days;
- result hit/miss after official settlement;
- flat-stake investment, return, profit and ROI;
- longest losing sequence;
- peak-to-trough drawdown;
- largest single-hit share of total return;
- venue/month distribution;
- core race-rank distribution;
- first-ticket vs second-ticket position in each V4 race.

A day with 12 valid Stage-1 candidates but no Stage-2 support is **not** a zero-candidate day. It is a valid candidate day with zero supported purchase opportunities under the frozen Stage-2 hypothesis.

## Fixed analysis views — no threshold sweep

Until the 30/50/100 milestones are reached, report only predeclared structural slices. Do not search arbitrary odds thresholds or repeatedly split the data until a profitable cell appears.

Required views:

1. all V4 core candidates — diagnostic benchmark only;
2. `MKT_LATE07_TOP2_SUPPORT_V1` supported candidates;
3. V4 race-rank buckets: 1-2 / 3-4 / 5-6;
4. ticket position within race: TOP1 candidate ticket vs TOP2 candidate ticket;
5. supported × race-rank bucket;
6. supported × ticket-position bucket.

These are reporting slices, not automatic BUY rules.

## Stake normalization

Primary research performance must use **flat 100 JPY per evaluated ticket** so model quality is not confused with bankroll sizing.

Variable stake such as 100/200/300 JPY by future S/A/B class is explicitly deferred. It may be studied only after enough prospective evidence exists and must be preregistered separately before using outcomes to define stake tiers.

No martingale, loss recovery, daily target chasing, or stake increase based on current-day P/L is allowed.

## Monthly profit feasibility

Monthly +30,000 / +50,000 JPY must be treated as a scaling feasibility question, not as proof of model quality.

For any fixed evaluated policy:

- investment = evaluated tickets × flat stake;
- profit = return - investment;
- ROI = return / investment;
- scaled profit is only a mathematical scenario unless the corresponding stake has been prospectively authorized and used.

Do not claim that a +50,000 JPY month is feasible merely because a small sample can be multiplied by a larger hypothetical stake.

At each milestone, report:

- observed flat-100-JPY profit;
- observed ROI;
- average supported tickets/day;
- zero-supported-day rate;
- drawdown and losing streak;
- payout concentration;
- the ROI and/or stake scale that would have been required for +30,000 and +50,000 JPY in the same number of days, clearly labeled **scenario only**.

## Milestone discipline

### 30 supported cases

Purpose: integrity and early signal only.

- verify prospective provenance;
- verify no BASELINE/historical contamination;
- report all fixed slices;
- no Production promotion;
- no threshold retune;
- no stake tier design from outcomes.

### 50 supported cases

Purpose: stability review.

- repeat the same fixed views;
- compare whether results are being driven by one venue, one rank bucket or one large payout;
- report drawdown / losing sequence / zero-supported-day rate;
- still no automatic Production promotion.

### 100 supported cases

Purpose: first serious purchase-policy review.

Review whether the frozen Stage-2 supported subset provides enough evidence to justify designing a separate, prospective BUY/stake experiment.

Even at 100 cases, promotion is not automatic. Any new BUY threshold, stake tier, LINE behavior or Production purchase logic requires a separate explicit-approval change.

## Old-system comparison

Compare the old system and V4 using separate dimensions rather than only one ROI number:

- candidate days / eligible days;
- candidate tickets/day;
- zero-candidate-day rate;
- supported purchase-opportunity days;
- realized flat-stake ROI;
- monthly ticket volume;
- monthly profit at the actually evaluated flat stake;
- longest losing streak;
- maximum drawdown;
- payout concentration.

The desired outcome is **more usable opportunities without sacrificing long-run economics**, not simply more tickets.

## Explicit anti-overfitting rules

Before 100 supported prospective cases:

- do not modify V4 coefficients because of realized payouts;
- do not modify the 0..7 minute market window;
- do not change TOP2 support into another market threshold based on observed ROI;
- do not add an odds minimum/maximum because a small sample looks better there;
- do not remove low-performing rank buckets after seeing outcomes;
- do not reconstruct missed Forward days;
- do not merge BASELINE, historical proxy and V4 prospective evidence into one ROI figure;
- do not increase stake to make the +50,000 JPY target appear achievable.

## Safety boundary

This document authorizes research reporting only.

No change to:

- Production v24/FINAL;
- V4 candidate formula;
- Course / Opponent / Motor2 coefficients;
- BUY/WATCH/SKIP;
- Railway Variables / Cron / services / volumes;
- Production DB schema or rows;
- LINE sends;
- Forward persistence;
- automated purchase;
- real stake amount.

`purchase_action=false` remains mandatory.

## Current decision

`BROAD_CANDIDATE_FEED_PRESERVE / 12_TICKETS_NOT_PURCHASE_QUOTA / ZERO_BUY_ALLOWED_WHEN_EVIDENCE_WEAK / NO_DAILY_PROFIT_CHASING / MONTHLY_30K_REFERENCE / MONTHLY_50K_STRETCH / FLAT_100_RESEARCH_NORMALIZATION / 30_50_100_MILESTONES / NO_THRESHOLD_SWEEP / NO_STAKE_RETUNE / NO_PRODUCTION_CHANGE`
