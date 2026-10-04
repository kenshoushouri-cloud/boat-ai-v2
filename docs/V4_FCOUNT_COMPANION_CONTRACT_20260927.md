# V4 F-count companion artifact contract — 2026-09-27

Status: `DESIGN ONLY / PURE CONTRACT / NO CAPTURE / NO PERSISTENCE`

## Goal

PR #397 preregistered a prospective diagnostic but actual Forward persistence
requires explicit approval. Before that boundary, define how future F-count
evidence can be attached without changing the formal V4 artifact.

## Design decision

Use a **separate companion artifact**. Do not add F-count fields to the formal
V4 core evidence stream.

The companion binds to:
- the already-frozen formal V4 canonical core SHA256;
- the exact same six core race IDs;
- the exact same daily ranks;
- the same current-V4 predicted head;
- target date and formal generation timestamp.

It then adds only:
- six F counts per core race;
- predicted-head F count;
- companion capture timestamp.

## Integrity

A companion fails closed unless:
- formal V4 prospective evidence is eligible;
- formal freeze is outcome-free and pre-deadline;
- companion capture is on target day, at/after 08:15 JST;
- companion capture is at/after the formal freeze;
- companion capture is before all six core deadlines;
- race set exactly equals the formal six;
- every race has exactly six non-negative integer F counts;
- purchase_action remains false.

The pure contract calls the existing formal-core canonical hash function, so the
F-count evidence is cryptographically linked to the V4 decision that existed
before results.

## Why separate

This preserves evidence separation:
- formal V4 candidate identity remains unchanged;
- F-count research cannot silently alter selector/rank/tickets;
- a failed/missing F-count companion does not rewrite or invalidate the formal
  V4 freeze;
- later diagnostic settlement can require both hashes explicitly.

## Current boundary

This PR creates no artifact and performs no capture. It contains only a pure
in-memory contract, tests and CI.

Not included:
- DB query;
- GitHub scheduled capture;
- Railway service/Cron;
- artifact upload/persistence;
- result settlement;
- coefficient;
- Production change;
- LINE/purchase.

Actual companion capture/persistence remains an explicit approval gate.

`FORMAL_V4_CORE_IMMUTABLE / FCOUNT_COMPANION_SEPARATE / HASH_BOUND / NO_PERSISTENCE / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`
