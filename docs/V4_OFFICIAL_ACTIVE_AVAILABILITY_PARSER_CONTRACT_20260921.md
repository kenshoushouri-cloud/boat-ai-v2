# Candidate Discovery V4 official active availability parser preregistration — 2026-09-21

Status: `RESEARCH_ONLY / PURE_OFFLINE / RACE_LEVEL_ACTIVE_V1 / SYNTHETIC_CONTRACT_FIXTURES / NO_PRODUCTION_WIRING / PURCHASE_FALSE`

## Purpose

The existing block-only parser can prove selected-race unavailability from preserved official evidence, but the availability guard can legitimately PASS only when every selected formal core race has race-scoped positive evidence.

Page existence, a race card, or a scheduled deadline is insufficient. The 2026-09-21 Toda pages demonstrate why: official race-specific pages may still render race cards and deadlines while the day is shown as postponed.

A separate official surface is therefore preregistered for positive evidence:

`https://www.boatrace.jp/owpc/pc/race/raceindex?hd=YYYYMMDD&jcd=XX`

Current official-surface observation on 2026-09-21 showed active venue race rows with an explicit `投票` action, while postponed Toda race rows were shown as `発売終了`. This is useful design evidence, but this Draft does not claim that synthetic fixtures substitute for preserved real raw official bytes.

## Input contract

`candidate_discovery_v4_official_active_parse_input_v1`

Required:

- target date;
- exact selected `race_id`;
- frozen selected-race deadline as `HH:MM` JST;
- timezone-aware observation time;
- optional source-displayed update time;
- canonical BOAT RACE venue race-index URL for the exact date/venue;
- exact preserved raw payload encoded as base64;
- expected SHA-256 of those exact bytes;
- one UTF-8 race-row excerpt that occurs exactly once in the preserved payload;
- unique evidence ID.

## PASS conditions

The parser emits `status=active / scope=race` only when all are true:

- observation is on the target date in JST and strictly before the frozen deadline;
- source URL date and venue match the selected race;
- raw SHA-256 matches;
- the bound excerpt identifies exactly the selected race and no other race row;
- the bound excerpt contains the exact frozen `HH:MM` deadline;
- the bound excerpt contains an explicit `投票` action;
- the bound excerpt contains none of `発売終了`, `中止`, or `順延`.

Anything else fails closed.

## Why this is separate from the block parser

Negative evidence can safely BLOCK from a whole-venue cancellation surface.

Positive evidence has a higher burden. A venue-level `発売中` marker alone is not enough to assert every selected race is active. This v1 therefore requires an isolated selected-race row with an explicit betting action.

## Remaining evidence gate

The implementation tests use synthetic contract fixtures only.

Before any Production-effect guard can consume this parser output, preserve and review real official raw fixtures from:

1. a genuinely active selected race before its deadline; and
2. a cancelled/postponed selected race for the same source shape.

Each real fixture must retain raw bytes, SHA-256, observation time and parser result. If the real HTML structure differs from the preregistered assumptions, update the parser in a reviewed Draft before Production wiring.

## Safety

No HTTP, DB, Railway, LINE, result/payout or purchase action exists in the parser.

`RACE_LEVEL_ACTIVE_ONLY / FAIL_CLOSED / REAL_RAW_FIXTURE_REQUIRED / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`
