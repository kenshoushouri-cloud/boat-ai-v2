# V4 top-five formal replay bridge — 2026-09-23

Status: `RESEARCH_ONLY / PURE_OFFLINE / TOP5_PRE_RESULT_ONLY / NO_RECONSTRUCTION / NO_PRODUCTION_CHANGE`

## Purpose

PR #372 merged pre-result observation of `research_ranked_tickets` top five
while leaving the formal core at exactly two tickets.

This bridge converts a future immutable formal V4 artifact plus an exact-six
final outcome set into the existing 1..5 point marginal-revenue evaluator
without manually copying ticket ranks.

## Required evidence

For each day:

- immutable V4 formal artifact;
- explicit SHA-256 of that artifact;
- `prospective_evidence_eligible=true`;
- `purchase_action=false`;
- freeze provenance showing no result/payout read;
- `generated_at_jst == freeze_provenance.completed_at_jst`;
- exactly six formal core races with ranks 1..6;
- exactly five pre-result `research_ranked_tickets` per core race;
- research ranks 1 and 2 exactly equal formal core_order 1 and 2;
- all rankings frozen before their race deadlines;
- exact same six race IDs in the supplied outcome set;
- every outcome status final;
- exact trifecta and payout.

Missing or cancelled formal races block the whole day. There is no 5R shrink,
synthetic zero, replacement race or later-date substitution.

## Output

The bridge delegates to `v4_point_count_marginal_revenue.py` and emits
cumulative 1/2/3/4/5-point strategy metrics:

- investment;
- gross return;
- profit;
- ROI;
- exact-hit rate;
- chronological max drawdown;
- Nth-point incremental return/profit/ROI.

## Evidence boundary

The bridge can only use ranks physically preserved before results.

For Sep18/Sep19 only ranks 1-2 were preserved, so this module does not alter
their historical 3-5 status. The first legitimate 1-5 observations begin with a
future formal artifact created after PR #372 entered main.

## Relationship to availability guard

The availability activation path remains separate.

Only days that produce a valid formal artifact and later have all six exact
final outcomes can enter point-count economics.

A cancelled frozen core race remains unevaluable for the whole day.

## Safety

`PURE_OFFLINE / EXACT_SIX / TOP5_PRE_RESULT_ONLY / NO_RESULT_AFTER_RECONSTRUCTION / NO_DB / NO_NETWORK / NO_LINE / PURCHASE_FALSE`
