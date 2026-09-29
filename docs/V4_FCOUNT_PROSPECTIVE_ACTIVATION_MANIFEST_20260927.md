# V4 F-count prospective activation manifest — design only

Status: `NO-OP / EXPLICIT APPROVAL REQUIRED / NO LIVE READ / NO PERSISTENCE`

This freezes the exact allowed activation scope if prospective F-count capture is separately approved later.

## Required ordering

For each **future** target day only:

1. formal V4 prospective freeze completes first;
2. formal canonical-core SHA256 is frozen;
3. take the exact formal six race IDs;
4. open a read-only DB transaction;
5. execute only:

`select race_id,lane,f_count from v2_race_entries where race_id=any(%s) order by race_id,lane`

6. require exactly 36 rows: six races × lanes 1..6;
7. require exact non-negative integer F counts;
8. require capture >=08:15 JST, >=formal freeze, and < every formal core deadline;
9. build the separate #398 hash-bound companion in memory;
10. persist only that separate companion artifact.

## Failure isolation

A missing/invalid F-count companion must **not**:
- alter the formal V4 artifact;
- fail or rewrite the formal candidate decision;
- change selector/rank/TOP6/TOP2;
- send LINE;
- enable BUY;
- create a partial companion.

Fail closed: no companion artifact for that day.

## Forbidden

- historical F-count backfill;
- historical F-count coefficient search;
- reading results/payouts/odds into the companion;
- reading races outside the formal six;
- DB INSERT/UPDATE/DELETE/schema operations;
- modifying the formal artifact to embed F counts;
- using companion success/failure to change current V4 purchase behavior.

## Stop conditions after any future activation

Stop prospective capture and review immediately if any occurs:
- formal-core hash mismatch;
- post-deadline capture;
- any DB write attempt;
- any result/payout field in the input path;
- any race/lane outside the exact formal six.

## Production invariants

No change is authorized to:
- Course 0.50;
- Opponent Pressure 1.0 first-place-only;
- Motor2 beta 0.06;
- temperature 2.20;
- selector fields;
- formal TOP6/TOP2;
- stake;
- `purchase_action=false`.

This manifest does not choose or activate a schedule. The actual live read/capture/persistence wiring remains an explicit user-approval action.

`FUTURE_ONLY / EXACT_36_READ_ONLY / FORMAL_FIRST / SEPARATE_HASH_BOUND_COMPANION / FAIL_ISOLATED / NO_BACKFILL / NOT_ACTIVATED`
