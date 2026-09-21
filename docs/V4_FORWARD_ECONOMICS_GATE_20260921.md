# V4 Forward economics review contract — 2026-09-21

Status: `RESEARCH_ONLY / DESCRIPTIVE_ONLY / NO_AUTO_PLAN_CHANGE / NO_RETUNING / PURCHASE_FALSE`

## Purpose

Subscription/infrastructure choices should not be driven by cost alone, and system quality should not be judged by hit rate alone.

This contract defines the evidence that will be reviewed at the formal V4 milestones before deciding whether higher-cost Railway or ChatGPT plans are economically justified.

It does **not** recommend a plan and never changes a subscription automatically.

## Inputs

The pure evaluator consumes formal prospective daily summaries only.

For each formal day:

- exact formal date;
- core race count;
- core ticket count;
- investment;
- gross return;
- profit;
- exact-hit races;
- head-hit races;
- ordered first+second prefix-hit races;
- third-only misses.

The formal shape remains two frozen core tickets per race.

The caller also supplies **operating cost allocated to the same evaluation period in JPY**. The module performs no FX lookup and no monthly extrapolation.

## Metrics

The evaluator reports:

- formal days / races / tickets;
- investment;
- gross return;
- wagering profit;
- ROI;
- exact/head/prefix/third-only descriptive counts;
- cumulative peak-to-trough drawdown from the formal daily profit sequence;
- net observed profit after the caller-supplied operating cost for that same period.

A positive observed net value is descriptive evidence only.

## Milestones

Race-count milestones are frozen as:

- <30 formal races: `PRE_30_INSUFFICIENT_SAMPLE`
- 30–49: `MILESTONE_30_DESCRIPTIVE_ONLY`
- 50–99: `MILESTONE_50_REVIEW`
- >=100: `MILESTONE_100_REVIEW`

No milestone automatically authorizes:

- Railway Pro -> Hobby;
- ChatGPT Plus -> Go;
- Railway Pro retention;
- ChatGPT Plus retention;
- automatic purchase;
- model/threshold/stake/candidate changes.

Human review remains required.

## Cost-pressure guards

The evaluator rejects evidence if cost pressure has changed any of:

- prediction threshold;
- stake;
- candidate count;
- result-after reconstruction policy;
- purchase safety.

This prevents a subscription-cost objective from contaminating the prospective betting evidence.

## Current formal evidence

The currently evaluated formal V4 corpus remains:

- 2026-09-18: 6 races / 12 tickets / -100 JPY / ROI 91.667%
- 2026-09-19: 6 races / 12 tickets / +1,020 JPY / ROI 185.000%
- combined: 12 races / 24 tickets / +920 JPY / ROI 138.333%
- maximum cumulative drawdown across these two daily points: 100 JPY

This is still:

`PRE_30_INSUFFICIENT_SAMPLE`

The current positive result is encouraging descriptive evidence, but it is not enough by itself to justify or reject any subscription/infra plan.

## Plan-change principle

October dates remain Go/No-Go checkpoints, not forced downgrade dates.

If later prospective evidence shows that the system's net economics materially exceed recurring Railway/ChatGPT costs while preserving safety and reproducibility, retaining higher-capability plans is acceptable.

Conversely, cost savings must never be manufactured by loosening thresholds, raising stake, increasing candidate count, deleting required evidence, or reducing safety.

## Safety

`DESCRIPTIVE_ONLY / HUMAN_REVIEW_REQUIRED / NO_AUTO_PLAN_CHANGE / NO_RETUNE / PURCHASE_FALSE`
