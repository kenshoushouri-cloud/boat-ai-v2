# Candidate Discovery V4 venue diagnostics — 2026-09-14

Status: **RESEARCH ONLY / DIAGNOSTIC ONLY / NO VENUE EXCLUSION / NO PRODUCTION CHANGE**

## Decision frozen before first scheduled V4 Forward

No boat-racing venue is excluded from Candidate Discovery V4 or `MKT_LATE07_TOP2_SUPPORT_V1` at the start of prospective evaluation.

The purpose of venue reporting is to detect persistent venue-specific weakness without using a small sample to create a profitable-looking exclusion after outcomes are known.

## Current V1 rule

Through the current global **100 Stage-2 supported prospective cases** review:

- all eligible venues remain in the V4 candidate universe;
- venue is not a Stage-1 eligibility gate;
- venue is not a Stage-2 support gate;
- venue ROI is diagnostic only;
- a weak venue cannot be removed because of current-study outcomes;
- a strong venue cannot receive a larger real stake because of current-study outcomes.

This preserves the already-frozen rule that the current Stage-2 V1 has no venue carveout.

## Required venue metrics

For each venue represented in prospective evidence, report separately:

### All V4 Stage-1 core tickets

- evaluated cases;
- evaluated days;
- hits / hit rate;
- flat-100-JPY investment;
- return / profit / ROI;
- largest single-hit return;
- largest single-hit share of venue returns.

### Stage-2 V1 supported `core_order=1`

Report the same metrics for only `MKT_LATE07_TOP2_SUPPORT_V1` supported cases.

Stage-1 12-ticket diagnostics and Stage-2 `core_order=1` support must remain separate.

## Interpretation guard

A low venue ROI is not enough to call the venue unprofitable when:

- sample size is small;
- one large payout materially changes ROI;
- only a short calendar block is represented;
- Stage-2 support coverage is sparse;
- result concentration can explain the apparent difference.

Venue tables should therefore be read as evidence accumulation, not as a ranking to optimize against.

## Future venue-exclusion experiment

After the current global 100-supported-case review, a venue may become an exclusion *hypothesis* only if a persistent weakness is visible and is not explained by obvious sample concentration.

Any such hypothesis must be frozen in a **separate prospective preregistration before subsequent outcomes**. The current evidence may identify a candidate hypothesis, but it may not both define and validate the exclusion.

A future venue exclusion still requires separate explicit approval before any Production candidate/BUY behavior changes.

## Safety

This venue diagnostic adds no:

- DB writes;
- Production selector/model/threshold changes;
- candidate removal or reranking;
- Stage-2 window/TOP2 changes;
- Railway changes;
- LINE sends;
- real stake changes;
- automated purchase.

`venue_exclusion_allowed=false`, `purchase_action=false`, and `promotion_allowed=false` remain fixed.

## Frozen decision

`ALL_VENUES_INCLUDED / VENUE_DIAGNOSTIC_ONLY / NO_EXCLUSION_THROUGH_CURRENT_100_SUPPORTED_REVIEW / SEPARATE_FUTURE_PROSPECTIVE_PREREGISTRATION_REQUIRED / NO_PRODUCTION_CHANGE`
