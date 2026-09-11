# Racer Course missing-row neutral fallback — research results 2026-09-11

Status: `SUPPORTS_FORWARD_SHADOW_REVIEW / NO_PRODUCTION_CHANGE`

This note records two read-only historical evaluations of the fixed Course missing-row neutral rule. It does not authorize Production use.

## Fixed rule

- v24 PRE BASE unchanged.
- Course coefficient fixed at 0.50; no coefficient search.
- exact race-date racer-by-course Top3 only.
- usable snapshot must be `created_at <= 08:15 JST` and strictly before race deadline.
- observed usable lanes are z-scored among observed lanes only.
- missing/unusable lanes get Course z=0, leaving their BASE raw strength unchanged.
- fewer than two usable observations or near-zero observed SD => no Course adjustment.
- no later-snapshot repair, odds, payout, ROI, DB writes, LINE or Production changes.

Broad-rule preregistration: `908462848b73440359fd239d8f75dc2fa8d3a009`.

## Broad historical replay — 2026-07-15..2026-09-10

Workflow: `Racer Course Missing Neutral OOS` run `34560829226` — SUCCESS.

Coverage:
- target races 9,126
- evaluable 9,081
- missing result 45
- observed safe Course lanes: n0=899, n1=42, n2=48, n3=69, n4=397, n5=2,423, n6=5,203
- 58 dates / 24 venues represented in MISSING1PLUS.

Paired deltas vs BASE; negative is better:

### ALL_ELIGIBLE n=9,081
- Brier: `-0.00486215`, 95% CI `[-0.00507865,-0.00464333]`
- LogLoss: `-0.16897557`, 95% CI `[-0.17537141,-0.16238614]`
- actual-ticket rank: `-3.9954`, 95% CI `[-4.2894,-3.7029]`
- Top1 4.67% -> 6.34%
- Top3 12.50% -> 16.09%
- Top5 19.07% -> 23.62%
- Top10 31.88% -> 38.52%.

### COMPLETE6 n=5,203
- Brier `-0.00594928`
- LogLoss `-0.21776012`
- rank `-5.7665`.

### MISSING1PLUS n=3,878
- Brier: `-0.00340357`, 95% CI `[-0.00371347,-0.00310191]`
- LogLoss: `-0.10352274`, 95% CI `[-0.11209681,-0.09465796]`
- rank: `-1.6191`, 95% CI `[-1.9838,-1.2478]`
- Top1 4.38% -> 5.88%
- Top3 12.64% -> 15.39%
- Top5 20.11% -> 22.74%
- Top10 34.19% -> 38.83%.

Predeclared broad status: `SUPPORTS_NEUTRAL_FALLBACK_FORWARD_RESEARCH_ONLY`.

Important limitation: this broad period overlaps the earlier study that established Course coefficient 0.50, so it is not claimed as independent coefficient OOS.

## Post-study temporal holdout — 2026-08-25..2026-09-10

The prior Course study endpoint was 2026-08-24. A separate temporal sensitivity plan was frozen before inspecting this subset's metrics:

Preregistration: `c7f7daf39eaa877fb605e43d52a978b206c87b89`.

Workflow: `Racer Course Missing Neutral PostStudy` run `34561048041` — SUCCESS.

Coverage:
- target races 2,580
- evaluable 2,567
- missing result 13
- observed safe Course lanes: n0=468, n1=0, n2=0, n3=5, n4=81, n5=581, n6=1,432
- MISSING1PLUS: 1,135 races / 17 dates / all 24 venues.

### ALL_ELIGIBLE n=2,567
- Brier `-0.00447885`, 95% CI `[-0.00487818,-0.00407646]`
- LogLoss `-0.16338119`, 95% CI `[-0.17545431,-0.15116336]`
- rank `-4.2591`, 95% CI `[-4.8298,-3.6852]`
- Top1 4.32% -> 6.04%
- Top3 11.45% -> 15.00%
- Top5 17.80% -> 22.59%
- Top10 30.89% -> 37.09%.

### COMPLETE6 n=1,432
- Brier `-0.00597090`
- LogLoss `-0.23443647`
- rank `-7.1020`.

### MISSING1PLUS n=1,135
- Brier `-0.00259636`, 95% CI `[-0.00312494,-0.00207466]`
- LogLoss `-0.07373260`, 95% CI `[-0.08888723,-0.05814922]`
- rank `-0.6722`, 95% CI `[-1.2899,-0.0370]`
- Top1 3.96% -> 5.46%
- Top3 11.81% -> 13.92%
- Top5 19.03% -> 21.76%
- Top10 32.86% -> 35.95%.

The post-study subset satisfies every predeclared sensitivity condition, so the project interpretation is:

`POSTSTUDY_HOLDOUT_SUPPORTS_FORWARD_SHADOW_REVIEW`.

## Decision boundary

The result supports implementing the fixed missing-row neutral rule in a **separate forward-shadow path only**. It does not authorize:
- Production v24/FINAL changes;
- Course coefficient changes;
- Opponent Pressure promotion;
- BUY/WATCH/SKIP or LINE changes;
- Railway Production deployment/config changes;
- automatic purchase.

A forward-shadow implementation must preserve the same fixed rule and collect natural prospective evidence before any Production promotion review.
