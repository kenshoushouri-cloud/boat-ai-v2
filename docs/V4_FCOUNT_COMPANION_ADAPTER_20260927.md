# V4 F-count companion pure adapter — 2026-09-27

Status: `STACKED ON #398 / DESIGN ONLY / NO I/O / NO PERSISTENCE`

## Purpose

Freeze the last transformation layer before any approved prospective capture.

The adapter accepts:
1. an already-frozen formal V4 prospective artifact;
2. caller-supplied rows shaped like `v2_race_entries(race_id,lane,f_count)`;
3. a caller-supplied capture timestamp.

It performs no DB query itself.

## Fixed normalization

- formal V4 must contain exactly six core races ranked 1..6;
- input must contain exactly 36 rows;
- race IDs must equal the formal six exactly;
- every race must contain lanes 1..6 exactly once;
- `lane` and `f_count` must be exact integers;
- `f_count >= 0`;
- rows carrying outcome-like keys are rejected;
- extra races, missing lanes and duplicates fail closed.

The future approved read is intentionally narrow:

`select race_id,lane,f_count from v2_race_entries where race_id=any(%s) order by race_id,lane`

This query string is a contract constant only. This PR does not execute it.

## Binding

After normalization the adapter calls the #398 companion contract and verifies:
- formal V4 canonical-core hash before == after;
- companion formal-core hash == formal V4 canonical-core hash;
- deterministic companion SHA256 can be derived.

## Boundary

No DB/network/file I/O, artifact upload, scheduled action, settlement, coefficient,
Production change, LINE or purchase is included.

Actual read/capture/persistence remains an explicit approval gate.

`PURE_ADAPTER_ONLY / EXACT_36_ROWS / HASH_BOUND / NO_CAPTURE / NO_PERSISTENCE / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`
