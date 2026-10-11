# V4 F-count prospective head-error diagnostic — 2026-09-27

Status: `PREREGISTERED DESIGN ONLY / NO COLLECTION / NO PERSISTENCE`

## Why F count is the next family

Result-blind PR #396 found:
- F count full-six coverage: 100%;
- within-race variation: 57.0741%;
- F>0 rows: 15.0826%;
- L count within-race variation: only 0.8221%.

The F family was prioritized before the novelty audit because it is a distinct
pre-race operational-state fact rather than another place-rate or motor-rate
transformation.

PR #395 also showed historical row-level 08:15 capture timestamps are absent.
Therefore this design does **not** authorize a retrospective F-count performance
test.

Current Production scheduling/source semantics show that daily data preparation
runs around 06:30 JST and obtains official BOAT RACE racelist entry data before
the current V4 08:15 source cutoff. That makes a new prospective freeze
technically feasible, but collection/persistence requires separate explicit
approval.

## Frozen question

Does current V4 make materially more first-place/head errors when its predicted
head has `F count >= 1` than when its predicted head has `F count = 0`?

No coefficient is defined.

## Prospective freeze contract

For each eligible future day:
- use the unchanged current V4 exact six core races;
- freeze after 08:15 JST and before every frozen race deadline;
- freeze all six non-negative integer F counts per core race;
- freeze current V4 predicted head and daily rank;
- no result, odds or payout read at freeze;
- exact six races required;
- purchase_action=false.

Primary population: all six current V4 core races, to accumulate evidence
without changing candidate selection.

Secondary diagnostic: daily-rank-1 only.

## Evidence gates fixed before collection

Do not interpret until:
- at least 200 finalized core races;
- at least 30 predicted-head F-positive races;
- at least 100 predicted-head F-zero races.

A future coefficient experiment may be *preregistered separately* only if:
- F-zero head accuracy exceeds F-positive head accuracy by at least 5.0 points;
- the same direction appears in at least 3 of 4 chronological quarters;
- all integrity/timing gates remain valid.

Passing this diagnostic does not select a coefficient and does not authorize
Production promotion.

## Current boundary

This PR contains only a pure validation/evaluation contract and tests.

It does **not**:
- schedule collection;
- write a DB/table;
- create a Forward artifact;
- send LINE;
- change V4;
- change candidate count/stake;
- buy anything.

Activating any prospective persistence/collection is a separate explicit user
approval gate.

`DESIGN_ONLY / NO_FORWARD_PERSISTENCE / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`
