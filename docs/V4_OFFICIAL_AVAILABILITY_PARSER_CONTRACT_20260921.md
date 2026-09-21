# Candidate Discovery V4 official availability parser preregistration — 2026-09-21

Status: `RESEARCH_ONLY / PURE_OFFLINE / BLOCK_ONLY_V1 / NO_PRODUCTION_WIRING / PURCHASE_FALSE`

## Purpose

PR #367 already preregisters the fail-closed availability guard. The remaining acquisition risk is proving that a normalized unavailable status actually came from an exact preserved BOAT RACE official payload.

This parser preregistration narrows v1 deliberately:

- it parses **unavailable/blocking evidence only**;
- it does not emit `active`;
- page existence, a deadline, a race card, or lack of a cancellation marker is never converted into positive availability evidence.

Positive race-level availability remains separate from this block-only parser. A dedicated `venue_race_index` active parser is now preregistered in `docs/V4_OFFICIAL_ACTIVE_AVAILABILITY_PARSER_CONTRACT_20260921.md`, but real preserved active/cancelled raw fixtures remain required before the guard can legitimately PASS all six races in Production.

## Input contract

`candidate_discovery_v4_official_unavailability_parse_input_v1`

Required identity:

- `source_kind`: `venue_day_index` or `race_page`;
- target date;
- exact selected `race_id`;
- timezone-aware observation time;
- optional source-displayed update time;
- canonical BOAT RACE official URL exactly matching the preregistered surface shape; unsupported extra path/query forms fail closed;
- exact preserved raw official payload encoded as base64;
- expected SHA-256 of those exact raw bytes;
- UTF-8 evidence excerpt that must occur exactly once in the preserved raw payload;
- unique `evidence_id`.

The parser computes SHA-256 itself before parsing.

## Supported negative evidence

### Venue/day index

Expected official surface shape:

`https://www.boatrace.jp/owpc/pc/race/index?hd=YYYYMMDD`

The exact bound excerpt must identify the expected official venue name, must not also contain another official venue name, and must contain either:

- a supported whole-venue unavailable marker: `中止順延` or `開催中止`; or
- a supported partial range marker matching `N R以降中止` for N=1..12.

Whole-venue output scope: `venue`.

Partial-range output scope: `venue_race_range` with `cancel_from_race_no=N`. A selected race before N is rejected rather than over-blocked.

### Race page

Expected official surface shape:

`https://www.boatrace.jp/owpc/pc/race/racelist?hd=YYYYMMDD&jcd=XX&rno=N`

URL date/venue/race number must match the frozen selected race.

The exact bound excerpt must contain:

- `レース中止`

Output scope: `race`.

## Why the excerpt is bound to raw bytes

The parser does not trust a free-standing parsed string. The human-readable evidence excerpt must occur **exactly once** inside the exact preserved UTF-8 raw payload whose SHA-256 is checked.

This is still a preregistered parser contract, not a claim that every possible BOAT RACE HTML layout or status vocabulary is covered. Official examples also include other status text such as plain `中止`; unsupported forms remain fail-closed until preserved fixtures and semantics are separately reviewed.

## Intentional limitation

v1 cannot emit:

`status=active`

That is deliberate. A positive PASS has a higher burden because a venue/day page that appears active does not prove every individual selected race is active.

Before Production use, the separately preregistered race-level positive parser must be validated against preserved real official active and cancelled/postponed fixtures and reviewed independently.

## Safety

The module:

- performs no HTTP request;
- reads no database;
- performs no Railway/GitHub/LINE operation;
- creates no candidate;
- reranks nothing;
- reads no result/payout;
- has no purchase path.

`BLOCK_ONLY_V1 / FAIL_CLOSED / NO_POSITIVE_INFERENCE / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`
