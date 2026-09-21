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

The formal evaluated-day shape is fixed to exactly six core races, exactly two frozen core tickets per race, and exactly 100 JPY per frozen ticket. The evaluator rejects a smaller denominator, extra/missing tickets, or a different stake rather than letting cost pressure alter the formal corpus.

Hit metrics must also reconcile structurally: exact hits <= first+second prefix hits <= head hits, and third-only misses cannot exceed the non-exact prefix-hit count.

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

## Milestone separation

This economics gate does **not** redefine the project's existing 30/50/100 prospective case milestones.

Those milestones currently belong to separately preregistered evidence tracks such as Stage2 supported cases and Primary-vs-Challenger prospective cases. Formal post-result race count must not be silently substituted for those case definitions.

Therefore this evaluator reports the formal settled race corpus and its economics, but returns:

- `project_milestones_redefined=false`
- `milestone_context_required_separately=true`

Any future 30/50/100 review must bring its own preregistered case-definition evidence alongside this economics summary.

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

The current corpus is still small descriptive formal evidence. It must not be relabeled as 12 Stage2 supported cases or 12 Primary-vs-Challenger milestone cases unless the relevant preregistered case contract independently says so.

The current positive result is encouraging descriptive evidence, but it is not enough by itself to justify or reject any subscription/infra plan.

## Plan-change principle

October dates remain Go/No-Go checkpoints, not forced downgrade dates.

If later prospective evidence shows that the system's net economics materially exceed recurring Railway/ChatGPT costs while preserving safety and reproducibility, retaining higher-capability plans is acceptable.

Conversely, cost savings must never be manufactured by loosening thresholds, raising stake, increasing candidate count, deleting required evidence, or reducing safety.

## Safety

`DESCRIPTIVE_ONLY / HUMAN_REVIEW_REQUIRED / NO_AUTO_PLAN_CHANGE / NO_RETUNE / PURCHASE_FALSE`
