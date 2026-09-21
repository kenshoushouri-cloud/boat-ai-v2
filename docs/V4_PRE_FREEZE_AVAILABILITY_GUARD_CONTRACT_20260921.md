# Candidate Discovery V4 pre-freeze official availability guard contract — 2026-09-21

Status: `RESEARCH_ONLY / PREREGISTERED / PURE_OFFLINE / NO_PRODUCTION_WIRING / PURCHASE_FALSE`

## Purpose

The 2026-09-21 formal V4 capture exposed a race-availability gap. BOAT RACE official same-day information showed Toda cancelled/postponed before the actual formal freeze, but the frozen structural core still included Toda 8R.

This document preregisters a future **eligibility guard**, not a replacement selector.

The guard may invalidate a not-yet-finalized formal artifact when one of its already-selected six core races is officially unavailable before that artifact's actual freeze. It must never remove the race and then re-rank or generate a replacement candidate using the later observation.

Before availability is considered, the pure guard also re-validates the structural identity of the formal core instead of trusting only a caller-provided eligibility flag:

- exactly six core race rows;
- exact daily ranks 1 through 6;
- exactly core orders 1 and 2 on each core race;
- race ID date equals artifact target date;
- race ID venue equals the row venue ID;
- race number is a two-digit value from 01 through 12.

Any mismatch fails closed. These checks do not select, remove, replace, or rerank a candidate.

No Production behavior is changed by this Draft.

## Evidence boundary

The 2026-09-21 historical artifact remains classified under the contract that existed when it was captured. This Draft does not retroactively relabel or reconstruct it.

Known incident identifiers:

- formal workflow run: `35549611949`
- artifact generated: `2026-09-21T10:03:12.277823+09:00`
- affected core race: `20260921_02_08` (Toda 8R)
- BOAT RACE official today's-race page update displayed: `08:25 JST`
- official classification observed: Toda `中止順延`

The finding is pre-result. No outcome, finish order or payout was used to identify the availability gap.

## Proposed snapshot contract

Caller-supplied snapshot contract:

`candidate_discovery_v4_official_availability_snapshot_v1`

The snapshot is intentionally **multi-source**. The official same-day index can provide venue/day unavailability, while race-level pages are separate `hd/jcd/rno` resources. A single top-level URL/digest must not be treated as provenance for six race-scoped positive assertions across multiple venues.

Top-level required fields:

- `target_date`
- non-empty `evidence_sources` list
- one unique status row for every selected formal core race

Each `evidence_sources[]` entry requires:

- unique `evidence_id`;
- timezone-aware `observed_at`;
- optional timezone-aware `source_updated_at` when the official surface exposes a source update timestamp;
- BOAT RACE official `source_url`;
- lowercase 64-hex `source_content_sha256` over the exact raw official content observed.

Examples of official surfaces with different evidence roles:

- venue/day overview: `https://www.boatrace.jp/owpc/pc/race/index?hd=YYYYMMDD`
- race-specific page: `https://www.boatrace.jp/owpc/pc/race/racelist?hd=YYYYMMDD&jcd=XX&rno=N`

Each `races[]` row requires:

- `race_id`
- `venue_id`
- normalized `status`
- evidence `scope`: `race` or `venue`
- `evidence_id` referencing a validated immutable source entry

Allowed normalized statuses in this first preregistration:

- `active`
- `cancelled_postponed`

Allowed evidence scopes:

- `race`: the referenced preserved official evidence directly classifies that exact race;
- `venue`: the referenced preserved official evidence classifies the whole venue/day and is applied to that selected race;
- `venue_race_range`: the referenced preserved official evidence declares a partial venue interruption such as `11R以降中止`; the row must carry `cancel_from_race_no` and may block only selected races at or after that race number.

Scope is safety-relevant. Venue-level `cancelled_postponed` is sufficient to block a selected race because the whole venue/day is unavailable. Venue-level `active` is **not** sufficient to pass an individual core race. A PASS therefore requires race-scoped `active` evidence for every selected core race.

A race-scoped positive evidence source may not be reused to assert another selected core race. Venue-wide unavailable evidence may be reused only across selected races at the same venue. Venue-range unavailable evidence may be reused only across selected races at the same venue that are all covered by the same `cancel_from_race_no`. A selected race before that boundary cannot be blocked by the range evidence. If one selected race carries whole-venue unavailable evidence while another selected race at the same venue is marked active, the snapshot is internally inconsistent and fails closed.

Anything else is fail-closed. Missing core race, duplicate race, duplicate/unknown evidence ID, unknown scope/status, race/venue mismatch, malformed digest, non-official source, incompatible evidence reuse, or inconsistent venue-wide evidence all fail closed.

The snapshot may contain additional non-core race rows, but all six exact frozen core race IDs must be present and must match their expected venue IDs. Extra rows do not enter the decision and cannot create a replacement candidate.

The pure module does not fetch or parse the BOAT RACE website. Acquisition/parsing and Production wiring remain separate review boundaries. The acquisition layer is responsible for demonstrating that the preserved raw source actually supports the declared normalized status and scope.

The official pages are mutable during the day. URL + parsed text/timestamp alone is insufficient provenance. A future acquisition layer must preserve the exact observed official payload (or equivalent immutable raw representation), compute `source_content_sha256` for each evidence source, and carry those source records into this snapshot contract.

## Timing rule

Every referenced evidence source must have been observed no later than the artifact's actual `generated_at`.

When an official surface exposes `source_updated_at`, that timestamp must be no later than the corresponding evidence `observed_at`. A page without an explicit source-update timestamp may omit `source_updated_at`; the preserved raw bytes plus pre-freeze observation time remain mandatory.

This availability observation has a different safety role from Course/Opponent feature cutoffs: it is not a predictive feature and must never improve ranking. It may only block an artifact whose already-selected core includes a race officially unavailable before freeze.

This asymmetry is intentional:

- availability known before actual freeze -> future guard may BLOCK the artifact;
- availability not known until after freeze -> do not retroactively reconstruct the core; post-result evaluation may later be unavailable;
- delayed scheduler execution must not gain replacement candidates from later availability knowledge.

## Non-constructive rule

If a selected core race is `cancelled_postponed`:

`BLOCK_PRE_FREEZE_UNAVAILABLE_CORE`

Mandatory consequences:

- no replacement candidate;
- no re-ranking;
- no denominator shrink from six races;
- no synthetic loss/payout;
- no later-date substitution;
- no result/payout read;
- `purchase_action=false`.

A future Production implementation should fail closed rather than trying to recover evidence volume.

## Pure implementation in this Draft

- `research/candidate_discovery_v4_availability_guard.py`
- `tests/test_candidate_discovery_v4_availability_guard.py`

The module consumes only already-supplied Python/JSON-compatible objects.

It has no:

- PostgreSQL/DB access;
- HTTP/network access;
- Railway access;
- GitHub API access;
- LINE send;
- purchase path;
- candidate generation/ranking path;
- Production mutation path.

## Required future work before any Production use

This Draft does **not** authorize wiring the guard into the formal V4 workflow.

Before any Production-effect use:

1. specify and test a timing-safe official BOAT RACE acquisition/parser path;
2. preserve every exact raw official observation/provenance item and deterministic SHA-256, and prove each evidence-source digest was computed from its preserved payload;
3. define behavior for official source outage, ambiguous text, partial venue coverage, venue-vs-race evidence scope and status changes;
4. prove the guard cannot change candidate ranking or create replacement candidates;
5. decide where the immutable availability snapshot is attached to the formal capture;
6. run prospective shadow evidence;
7. obtain explicit approval for any Production candidate/capture eligibility behavior change;
8. only then consider merge/deploy/wiring.

## Safety

`RESEARCH_ONLY / FAIL_CLOSED / NO_REPLACEMENT / NO_RERANK / NO_RESULT_AFTER_RECONSTRUCTION / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`
