# V4 capture resilience preregistration

Status: `RESEARCH_ONLY / FUTURE_DATES_ONLY / NO_BACKFILL / NO_PRODUCTION_MUTATION`

Date frozen: 2026-09-15 JST

## Incident that motivates this plan

The first scheduled formal Candidate Discovery V4 prospective freeze was expected at 08:16 JST on 2026-09-15 from default branch `main`.

The workflow file was present on `main`, had the intended `16 23 * * *` cron, read-only PostgreSQL guard, `purchase_action=false`, pre-deadline checks, and immutable artifact hashing. Other scheduled workflows on the same main SHA executed normally later that morning, but no `Candidate Discovery V4 Prospective Freeze` scheduled run appeared for the 2026-09-15 capture window.

Therefore 2026-09-15 formal V4 prospective evidence is permanently classified:

`UNAVAILABLE / MISSING_SCHEDULED_CAPTURE`

It must never be regenerated, backfilled, or relabeled as prospective after the fact.

## Goal

Prevent a scheduler miss from silently losing another full Forward day without weakening the evidence contract.

This plan applies only to future dates after it is explicitly adopted. It does not authorize a Production model, DB, Railway, LINE, purchase, threshold, or staking change.

## Invariants

Any primary or fallback capture must retain all current V4 safety requirements:

- target date equals current JST date;
- source cutoff is 08:15 JST;
- generation starts only after the source cutoff;
- scheduled/evaluable universe is complete;
- exactly 6 core races / 12 core tickets;
- every frozen row is generated before the earliest relevant race deadline;
- no result/payout table may be read;
- `prospective_evidence_eligible=true`;
- `purchase_action=false`;
- `promotion_allowed=false`;
- DB session remains read-only;
- immutable artifact + SHA-256;
- no result-after reconstruction.

## Proposed resilient capture contract

### Primary channel

Keep the existing GitHub scheduled capture at 08:16 JST.

### Independent fallback channel

Use a second scheduler that is operationally independent of the primary GitHub scheduled event. Candidate implementations, in preferred order for review:

1. a small read-only Railway Cron dedicated to V4 evidence capture;
2. a pre-registered exact-time orchestration task that dispatches the existing GitHub `workflow_dispatch` only when the primary run is missing;
3. a second GitHub schedule only as a weaker fallback because it shares the same scheduler failure domain.

The fallback should check at approximately 08:25 JST. It may capture only when all original prospective guards can still pass. If timing is no longer safely pre-deadline, it must fail closed and mark that date unavailable.

No fallback may use results, payouts, post-race data, or a reconstructed candidate set.

## Daily official-artifact rule

For any future date with more than one valid pre-result capture, define the official V4 Forward artifact prospectively as:

1. valid safety contract required;
2. earliest `generated_at_jst` after 08:15 JST;
3. tie-break by lower GitHub/Railway run identifier where needed.

Any later valid capture is diagnostic-only and must not be mixed into formal Forward scoring.

If the primary succeeds, fallback should no-op where technically possible. If duplicate execution still occurs, the earliest-valid rule removes ambiguity without changing predictions after outcomes.

## Monitoring requirement

A daily read-only audit should record:

- target date;
- primary run present/missing;
- fallback invoked/not invoked;
- capture channel;
- run ID / head SHA;
- generated_at_jst;
- earliest relevant deadline;
- 6-race / 12-ticket completeness;
- artifact ID/name;
- SHA-256;
- `prospective_evidence_eligible`;
- `purchase_action`;
- final classification: `FORMAL_AVAILABLE` or `UNAVAILABLE`.

A missing day is acceptable evidence. A reconstructed day is not.

## Adoption gate

Before any fallback scheduler is activated:

- choose exactly one independent fallback mechanism;
- review its permission boundary;
- prove it cannot write Production DB or send LINE/purchase actions;
- add contract tests for primary/fallback artifact equivalence under identical source inputs;
- preregister the official-artifact rule on `main` before the next date it is used;
- obtain any explicit Railway Production approval if a Railway Cron/service is selected.

Current decision:

`2026-09-15_UNAVAILABLE / FUTURE_CAPTURE_RESILIENCE_PREREGISTERED / NO_BACKFILL / NO_FALLBACK_ACTIVATED_YET / PURCHASE_FALSE`
