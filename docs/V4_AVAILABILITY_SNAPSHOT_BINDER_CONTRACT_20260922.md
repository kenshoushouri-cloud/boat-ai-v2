# Candidate Discovery V4 availability raw-to-snapshot binder — 2026-09-22

Status: `RESEARCH_ONLY / PURE_OFFLINE / RAW_SHA_VERIFY / EXACT_SIX_BINDING / NO_PRODUCTION_WIRING / PURCHASE_FALSE`

## Purpose

This binder removes the remaining human-normalization gap between a pre-freeze raw capture and the availability guard.

Input:

1. immutable V4 formal artifact;
2. pre-freeze availability raw manifest;
3. exact preserved raw source bytes.

Output:

`candidate_discovery_v4_official_availability_snapshot_v1`

The binder performs no HTTP and no DB access.

## Binding sequence

For every frozen core race:

1. verify the raw manifest target/timing contract;
2. recompute every raw source SHA-256;
3. require capture completion and each source observation no later than the artifact freeze;
4. inspect the preserved same-day index for an isolated whole-venue/range cancellation row;
5. if no venue-wide blocker exists, inspect the preserved venue `raceindex` for exactly one row matching the frozen race number and deadline;
6. delegate normalization to the existing unavailable or active parser;
7. emit exactly six race rows and only the raw sources actually referenced.

One pre-freeze venue `raceindex` source may bind multiple core races from that venue because each active race carries a distinct row-level `evidence_binding_sha256`.

## Fail-closed conditions

Examples:

- raw capture finished after artifact freeze;
- source observation after freeze;
- raw SHA mismatch;
- missing venue source;
- ambiguous duplicate race row;
- frozen deadline mismatch;
- missing explicit `投票`;
- malformed cancellation row;
- result/payout-read invariant drift.

The binder never supplies a replacement candidate and never converts an ambiguous row into active.

## Remaining gate

Synthetic fixtures prove the pure contract only.

Before Production wiring, a future timing-clean pre-freeze capture must supply real BOAT RACE raw bytes. Those bytes must pass:

`raw capture -> binder -> parser -> guard`

without hand-editing status/scope.

## Safety

`PURE_OFFLINE / EXACT_RAW_SHA / EXACT_SIX / NO_RESULT_READ / NO_PAYOUT_READ / NO_RERANK / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`
