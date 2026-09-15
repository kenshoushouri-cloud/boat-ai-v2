# V4 capture resilience preregistration

Status: `RESEARCH_ONLY / FUTURE_DATES_ONLY / NO_BACKFILL / NO_PRODUCTION_MUTATION`

Date frozen: 2026-09-15 JST

## Incident that motivates this plan

The first scheduled formal Candidate Discovery V4 prospective freeze was expected at **08:16 JST** on 2026-09-15 from default branch `main`.

The workflow file was present on `main`, had the intended `16 23 * * *` cron, read-only PostgreSQL guard, `purchase_action=false`, pre-deadline checks, and immutable artifact hashing.

The scheduled event eventually appeared as GitHub Actions run **`34917166205`**, but not until **10:25 JST**:

- event: `schedule`
- main SHA: `61f7d6e75629ffb549a583f00bfd5dd58c186a71`
- scheduled target resolved correctly to `2026-09-15`
- freeze started: `2026-09-15T10:25:18.860949+09:00`
- freeze completed its candidate-feed computation at approximately `10:25:20 JST`
- earliest frozen-feed deadline: `2026-09-15T09:36:00+09:00`
- scheduler delay relative to the planned 08:16 start: approximately **2 h 9 min**

The inner read-only candidate feed produced 6 core races / 12 core tickets and read no result or payout rows, but the prospective wrapper correctly rejected the run because it was already after the earliest frozen-feed deadline:

`RuntimeError: prospective freeze was not completed before earliest frozen-feed deadline`

The immutable prospective artifact upload step was skipped. The late-generated candidate list is diagnostic only and must never be scored as formal prospective evidence.

Therefore 2026-09-15 formal V4 prospective evidence is permanently classified:

`UNAVAILABLE / LATE_SCHEDULED_CAPTURE_REJECTED_PREDEADLINE_GUARD`

This supersedes the earlier provisional classification `MISSING_SCHEDULED_CAPTURE`. It must never be regenerated, backfilled, or relabeled as prospective after the fact.

## Goal

Prevent scheduler delay or scheduler miss from silently losing another full Forward day without weakening the evidence contract.

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

The 2026-09-15 incident proves that GitHub scheduled execution can be delayed far beyond the safe evidence window. The primary therefore must not be the only capture channel.

### Independent fallback channel

Use a second scheduler that is operationally independent of the primary GitHub scheduled event. Candidate implementations, in preferred order for review:

1. a small read-only Railway Cron dedicated to V4 evidence capture;
2. a pre-registered exact-time orchestration task that dispatches the existing GitHub `workflow_dispatch` only when the primary run is missing;
3. a second GitHub schedule only as a weaker fallback because it shares the same scheduler failure domain.

The fallback should check at approximately **08:25 JST**, leaving substantial headroom before the observed 09:36 earliest deadline on the incident date. This time is an operational resilience checkpoint, not a model threshold.

It may capture only when all original prospective guards can still pass. If timing is no longer safely pre-deadline, it must fail closed and mark that date unavailable.

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
- primary run present/missing/late;
- primary scheduled-vs-start delay;
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

A missing or late-rejected day is acceptable evidence. A reconstructed day is not.

## Adoption gate

Before any fallback scheduler is activated:

- choose exactly one independent fallback mechanism;
- review its permission boundary;
- prove it cannot write Production DB or send LINE/purchase actions;
- add contract tests for primary/fallback artifact equivalence under identical source inputs;
- preregister the official-artifact rule on `main` before the next date it is used;
- obtain any explicit Railway Production approval if a Railway Cron/service is selected.

Current decision:

`2026-09-15_UNAVAILABLE_LATE_GITHUB_SCHEDULE / FAIL_CLOSED_WORKED / FUTURE_CAPTURE_RESILIENCE_PREREGISTERED / NO_BACKFILL / NO_FALLBACK_ACTIVATED_YET / PURCHASE_FALSE`
