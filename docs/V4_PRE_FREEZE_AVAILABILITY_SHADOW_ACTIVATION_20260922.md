# V4 pre-freeze availability shadow capture activation — 2026-09-22

Status: `APPROVED_SHADOW_CAPTURE / PRODUCTION_WORKFLOW_WIRING / NO_ELIGIBILITY_EFFECT / PURCHASE_FALSE`

## Approval scope

The user explicitly approved wiring the preregistered pre-freeze availability
capture into the current-main V4 workflow.

This activation intentionally stops short of changing V4 candidate eligibility.

## Runtime order

For scheduled or fallback-dispatched V4 workflow runs:

1. resolve current JST target date;
2. load PostgreSQL URL using the existing workflow mechanism;
3. read the same-day `v2_races` universe under an explicit read-only transaction;
4. derive deterministic venue set, earliest scheduled deadline and
   `race_universe_sha256`;
5. capture the BOAT RACE official same-day index plus one venue `raceindex`
   page per scheduled venue;
6. upload the exact raw files + manifest as a separate immutable Actions artifact;
7. continue the existing V4 prospective freeze unchanged.

## Shadow-only failure policy

Availability collection is evidence collection only at this stage.

A failure to capture official raw:

- is recorded in the workflow log;
- does not fabricate evidence;
- does not change the six-race candidate core;
- does not suppress the existing formal freeze;
- does not change fallback artifact recognition;
- does not authorize replacement/rerank.

This avoids making Production eligibility depend on an unvalidated real-HTML
parser before the first timing-clean raw fixture is reviewed.

## Artifact

Successful capture artifact name:

`candidate-discovery-v4-availability-raw-<github_run_id>`

It contains:

- exact official raw files;
- `manifest.json`;
- deterministic capture request;
- capture log.

The existing formal freeze artifact retains its original exact name, so the
Railway fallback dispatcher continues to recognize only a completed formal
prospective-freeze artifact.

## Promotion boundary

After at least one real timing-clean capture is retained:

1. replay the exact bytes through the raw-to-snapshot binder;
2. verify the existing parsers against real HTML;
3. document any format mismatch;
4. only then consider activating availability as a candidate-eligibility guard.

Activating the guard changes candidate eligibility and remains a separate
Production-effect decision.

## Safety

`READ_ONLY_DB / OFFICIAL_AVAILABILITY_ONLY / RAW_SHA / SHADOW_ONLY / NO_RESULT_READ / NO_PAYOUT_READ / NO_DB_WRITE / NO_RERANK / NO_PURCHASE`
