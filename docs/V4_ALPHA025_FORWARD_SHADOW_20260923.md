# V4 alpha=0.25 prospective shadow — 2026-09-23

Status: `PREREGISTERED / DISABLED_PENDING_#374_GATE / PROSPECTIVE_ONLY / NO_PRODUCTION_CHANGE`

## Frozen hypothesis

Historical tuning is closed.

The only challenger carried forward is:

- current V4 daily six-race selector unchanged;
- current full P(first) marginal unchanged;
- historical position-conditional second/third model weights frozen;
- convex blend alpha fixed at **0.25**;
- formal evaluation remains exactly two tickets per race.

No narrower alpha search or coefficient adjustment is permitted on the same historical
2025-07-01..2026-09-22 sample.

Historical source of the hypothesis:

- run `35850876154`;
- artifact `10745995595`;
- ZIP SHA-256 `6aae27dbaa9ed7a13a937904765b61124d4507ec52880d007e9998e1286debbe`;
- historical selected-policy Top2 delta +0.558pp;
- nine-block bootstrap 95% interval still crossed zero, so this is **not**
  Production promotion evidence.

## Prospective freeze contract

A forward freeze is valid only when all conditions hold:

1. target date is the actual current JST date;
2. freeze occurs at or after 08:15 JST;
3. current V4 exact six races are available;
4. every selected race deadline is strictly after the freeze timestamp;
5. only pre-result race-card / Course / Opponent / Motor inputs are read;
6. results, payouts, odds and legacy market rows are not read;
7. current Top2 and alpha=0.25 shadow Top2 are written only to the workflow artifact;
8. PostgreSQL transaction is READ ONLY;
9. no DB persistence, LINE, purchase, promotion or Production behavior change occurs.

The artifact records the target date, freeze timestamp, frozen model hash, current
Top2, shadow Top2 and whether the two differ.

## #374 ordering dependency

The workflow is checked in with:

`V4_ALPHA025_FORWARD_ENABLED: '0'`

and must remain disabled until the 2026-09-24 real timing-clean #374 availability
gate is completed.

After that gate:

- refetch main and #374 state;
- if #374 merges under the existing approval, rebase this PR onto the new main;
- reconcile the prospective generator with the merged availability behavior;
- rerun exact-head CI;
- only then set the research workflow enable flag for a same-day prospective freeze.

This prevents a shadow freeze from being based on a stale pre-availability contract.

## Evaluation boundary

Forward persistence to Production DB remains approval-gated. The intended evidence
surface is a sanitized CI artifact only.

After official results become available, an offline evaluator may compare the frozen
tickets against exact official outcomes. It must never reconstruct or rerank tickets
after seeing results.

No historical or prospective result here can directly change Production.

`ALPHA_025_FROZEN / HISTORY_TUNING_CLOSED / SAME_DAY_PRE_RESULT / RESULT_READ_0 / ODDS_READ_0 / DB_WRITE_0 / LINE_0 / BUY_0 / PURCHASE_FALSE`
