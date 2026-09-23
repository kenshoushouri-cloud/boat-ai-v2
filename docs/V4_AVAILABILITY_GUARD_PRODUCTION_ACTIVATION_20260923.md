# Candidate Discovery V4 availability guard Production activation — 2026-09-23

Status: `USER_APPROVED / PREPARED_FOR_REAL_FIXTURE_VALIDATION / FAIL_CLOSED / PURCHASE_FALSE`

## Approval

The user explicitly approved proceeding with Production-effect wiring after the
pre-freeze availability capture/parser/binder design was completed.

This activation is intentionally prepared before the first real timing-clean
fixture, but must not be merged solely on synthetic tests. The first real
pre-freeze raw artifact from the already-merged shadow capture must pass the
same binder/parser/guard chain before merge.

## Production behavior after activation

Scheduled and fallback-dispatched V4 runs execute in this order:

1. resolve current JST target date;
2. read the same-day race universe under the existing read-only PostgreSQL path;
3. capture the official same-day index plus venue raceindex raw pages;
4. preserve raw bytes, SHA-256 and observation times;
5. run the existing prospective V4 freeze unchanged;
6. bind the frozen six core races to the preserved pre-freeze raw;
7. evaluate the exact-six availability guard;
8. upload the normal formal prospective artifact **only when**
   `PASS_ACTIVE_CORE`.

The guard remains non-constructive.

It never:

- removes one race and chooses another;
- reranks;
- changes model/coefficient/threshold/stake/candidate count;
- reads results or payouts;
- writes PostgreSQL;
- sends LINE;
- purchases.

## Fail-closed behavior

Any of the following blocks the normal formal artifact:

- pre-freeze raw capture failure;
- raw/request/manifest identity mismatch;
- raw SHA mismatch;
- raw observation after artifact freeze;
- missing or ambiguous official race row;
- unsupported official status;
- selected core race officially cancelled/postponed before freeze;
- missing explicit race-level active evidence;
- binder/parser/guard exception.

When blocked, the generated candidate core is retained only inside a separate
diagnostic availability-guard artifact. It is **not** uploaded under the normal
`candidate-discovery-v4-prospective-freeze-<run_id>` artifact name.

This is important because the Railway fallback dispatcher recognizes the normal
formal artifact name. A blocked primary therefore remains absent to the
fallback checkpoint rather than being mistaken for a valid formal capture.

Fallback runs execute the same guard. They cannot bypass a cancellation or
availability-evidence failure.

## Evidence artifacts

Raw capture:

`candidate-discovery-v4-availability-raw-<run_id>`

Guard diagnostic:

`candidate-discovery-v4-availability-guard-<run_id>`

Formal prospective artifact, PASS only:

`candidate-discovery-v4-prospective-freeze-<run_id>`

## Timestamp schema hardening

The real prospective artifact uses `generated_at_jst` and
`freeze_provenance.completed_at_jst`.

The guard and binder now use the canonical field and require freeze completion
to match it. The earlier synthetic-only `generated_at` assumption is no
longer relied upon.

## Partial cancellation

For an official venue marker such as `11R以降中止`:

- selected races before R11 continue to race-level active validation;
- selected races R11 and later are blocked by the range evidence.

The whole day is still ineligible whenever any of the exact six frozen core
races is blocked. There is no five-race denominator shrink.

## Merge gate

Before merge:

1. all PR CI must pass;
2. the first real timing-clean raw capture from current main must exist;
3. exact raw bytes must replay successfully through the activation branch
   binder/parser/guard;
4. real HTML must not require hand-editing normalized status/scope;
5. raw and formal artifact timing must prove raw observation preceded freeze.

If the real fixture exposes an HTML mismatch, update the Draft and retest
instead of weakening the parser.

## Safety

`EXPLICIT_USER_APPROVAL / REAL_FIXTURE_BEFORE_MERGE / FAIL_CLOSED / EXACT_SIX / NO_REPLACEMENT / NO_RERANK / NO_RESULT_READ / NO_PAYOUT_READ / NO_DB_WRITE / PURCHASE_FALSE`
