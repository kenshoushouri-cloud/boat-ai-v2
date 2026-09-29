# V4 F-count live companion activation — 2026-09-30

Status: `APPROVED / PENDING_MERGE / FUTURE_ONLY / PRODUCTION_DECISION_UNCHANGED`

## Approval

On 2026-09-30 JST, the user explicitly approved proceeding with the work needed to maximize the chance of a mid-October operational start.

This approval is applied narrowly to:
- prospective F-count companion collection for future target days;
- the already-preregistered separate companion artifact contract;
- no historical backfill;
- no model/selector/threshold/stake/LINE/purchase change.

## Activation design

The active Candidate Discovery V4 prospective-freeze workflow remains the formal evidence path.

For each future day:
1. pre-freeze availability capture runs;
2. formal V4 prospective freeze runs;
3. availability guard passes;
4. immutable formal V4 artifact is uploaded;
5. only then the optional F-count companion collector runs;
6. it reads exactly `race_id,lane,f_count` for the formal six races;
7. it requires exactly 36 rows and lanes 1..6 for every race;
8. it binds the companion to the formal canonical-core SHA256;
9. it uploads a separate F-count artifact only if every check passes.

## Failure isolation

F-count collection is `continue-on-error`.

If F-count is unavailable, malformed, late, hash-mismatched, or otherwise invalid:
- formal V4 remains valid if its own guard passed;
- formal V4 is not rewritten;
- TOP6/TOP2 are not changed;
- no rerank/replacement occurs;
- no LINE behavior changes;
- no purchase occurs;
- no partial F-count artifact is uploaded.

## Database contract

Transaction: READ ONLY.

Only allowed prospective read:

`select race_id,lane,f_count from v2_race_entries where race_id=any(%s) order by race_id,lane`

Forbidden:
- result/payout/odds reads;
- historical F-count backfill;
- historical F-count coefficient search;
- INSERT/UPDATE/DELETE/schema changes.

## Production invariants

Unchanged:
- Course coefficient 0.50;
- Opponent Pressure coefficient 1.0 first-place-only;
- Motor2 beta 0.06;
- probability temperature 2.20;
- selector head_p1/head_margin/top3_mass/concentration;
- formal TOP6;
- formal TOP2;
- current LINE behavior;
- stake;
- `purchase_action=false`.

## Why activate now

Historical replay has uneven feature coverage and cannot recreate future timing-clean evidence after the fact.

Starting future-only F-count capture now:
- preserves data that would otherwise be permanently missed;
- does not consume the 2026-10-15 V5 core scope;
- creates a clean V5.1 evidence stream in parallel;
- does not force F-count into the V5 core or Production model.

## Rollback

Rollback is code-only:
- remove/disable the optional F-count companion steps;
- formal V4 workflow continues unchanged;
- no DB cleanup is needed because the collector performs no DB writes.

`APPROVED_FUTURE_CAPTURE_ONLY / FORMAL_FIRST / EXACT_36_READ_ONLY / SEPARATE_ARTIFACT / FAILURE_ISOLATED / NO_BACKFILL / NO_MODEL_CHANGE / NO_LINE_CHANGE / PURCHASE_FALSE`
