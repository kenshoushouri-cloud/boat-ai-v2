# Combined manual Forward checkpoint — 2026-09-27

Purpose: reduce the post-nightly refresh to one manual workflow.

The combined workflow reuses the already-merged contracts:
- provider-selected immutable formal V4 checkpoint;
- frozen S03_M2 checkpoint;
- frozen review-gate helper.

It remains **manual only**:
- `workflow_dispatch`;
- optional `end_date=YYYY-MM-DD`;
- no schedule.

Execution order:
1. freeze provider run inventory before any result access;
2. materialize/hash-check only selected formal V4 artifacts;
3. settle frozen V4 against official results in a READ ONLY DB transaction;
4. run frozen S03_M2 under strict stored pre-deadline timing in a READ ONLY DB transaction;
5. combine both outputs locally;
6. compute only the already-frozen review-gate status.

The combined scorecard reports:
- V4 resolved formal days / TOP2 economics / next 10-20-30 gate;
- S03 evaluated/invalid/pending / economics / next 100 gate;
- no automatic promotion.

No selector/model/threshold/stake change, no DB write, no Railway config mutation, no LINE, no BUY.

For 2026-09-27, operational use should be after the natural nightly-results pipeline has completed; recent evidence supports checking after ~23:45 JST.

`MANUAL_ONLY / ARTIFACT_FIRST / READ_ONLY / SAME_FROZEN_RULES / GATES_ONLY / PURCHASE_FALSE`
