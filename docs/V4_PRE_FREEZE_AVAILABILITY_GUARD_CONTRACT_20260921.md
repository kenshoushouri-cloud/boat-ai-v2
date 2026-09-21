# Candidate Discovery V4 pre-freeze official availability guard contract — 2026-09-21

Status: `RESEARCH_ONLY / PREREGISTERED / PURE_OFFLINE / NO_PRODUCTION_WIRING / PURCHASE_FALSE`

## Purpose

The 2026-09-21 formal V4 capture exposed a race-availability gap. BOAT RACE official same-day information showed Toda cancelled/postponed before the actual formal freeze, but the frozen structural core still included Toda 8R.

This document preregisters a future **eligibility guard**, not a replacement selector.

The guard may invalidate a not-yet-finalized formal artifact when one of its already-selected six core races is officially unavailable before that artifact's actual freeze. It must never remove the race and then re-rank or generate a replacement candidate using the later observation.

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

Required fields:

- `target_date`
- timezone-aware `observed_at`
- timezone-aware `source_updated_at`
- BOAT RACE official `source_url`
- one unique status row for every selected formal core race, including its expected venue ID

Allowed normalized statuses in this first preregistration:

- `active`
- `cancelled_postponed`

Anything else is fail-closed. A missing core race, duplicate race, or race/venue mismatch is also fail-closed. Race-level granularity is required so one cancelled race can be represented without falsely cancelling or activating another core race at the same venue.

The pure module does not fetch or parse the BOAT RACE website. Acquisition/parsing, immutable storage/hash, and Production wiring remain separate review boundaries.

## Timing rule

The availability snapshot must have been observed no later than the artifact's actual `generated_at`.

The official source update time must be no later than the observation time.

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
2. preserve raw official observation/provenance and deterministic hash;
3. define behavior for official source outage, ambiguous text, partial venue coverage and status changes;
4. prove the guard cannot change candidate ranking or create replacement candidates;
5. decide where the immutable availability snapshot is attached to the formal capture;
6. run prospective shadow evidence;
7. obtain explicit approval for any Production candidate/capture eligibility behavior change;
8. only then consider merge/deploy/wiring.

## Safety

`RESEARCH_ONLY / FAIL_CLOSED / NO_REPLACEMENT / NO_RERANK / NO_RESULT_AFTER_RECONSTRUCTION / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`
