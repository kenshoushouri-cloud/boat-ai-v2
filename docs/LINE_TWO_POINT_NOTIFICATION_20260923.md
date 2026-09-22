# LINE final BUY notification main/cover display — 2026-09-23

Status: `USER_APPROVED / PRODUCTION_EFFECT / NOTIFICATION_ONLY / NO_THRESHOLD_CHANGE / NO_PURCHASE`

## User request

The user explicitly approved changing the actual LINE notification so a race can
show a main point and a cover point instead of presenting a single ticket as if
it were the entire recommendation.

## Important scope boundary

The current Production LINE path is the legacy/final realtime path:

`cron-final-check -> run_final_pg.py -> v25_final_realtime_pipeline_pg.py -> v23_line_notifier_batch_pg.py`

It reads existing `v2_realtime_decisions` rows with
`recommendation='buy'`.

This change **does not manufacture a second ticket** and does not lower a BUY
threshold.

For each race:

- first distinct existing BUY ticket in final-score order = `本線`;
- second distinct existing BUY ticket = `押さえ`;
- third and later BUY tickets are not notified;
- if only one BUY ticket exists, LINE explicitly says
  `押さえ: BUY条件該当なし`;
- if the main ticket was already sent and a second BUY becomes eligible later,
  that later ticket is labeled `押さえ`.

Duplicate identical tickets from different modes do not consume the two-point
limit.

## Why this is safe

This is a notification-layout change over already-existing BUY decisions.

It does not change:

- model/coefficient;
- probability calculation;
- BUY threshold;
- odds threshold;
- candidate generation;
- stake;
- automatic purchase behavior;
- V4 formal core;
- Railway Variables/Cron/service/volume;
- Production schema.

The helper module is pure and has no DB/network/purchase surface.

## Batch visibility correction

The existing batch notifier could format only `MAX_ITEMS_PER_MESSAGE` entries
but then mark every fetched decision as notified.

The new behavior marks only decisions from race groups that were actually
visible in the LINE body. Deferred race groups remain unnotified and may be
sent on a later natural cron.

## Relationship to V4

Candidate Discovery V4 already uses two formal core tickets per race.

This LINE change does **not yet claim that the realtime LINE tickets are the
same as V4 `core_order 1/2`**. The realtime LINE path and V4 formal artifact
remain separate evidence/decision paths.

A future exact V4-to-LINE integration would require an explicit evidence-bound
join to the immutable V4 formal artifact and should not be inferred from this
display change.

## Safety

`EXISTING_BUY_ONLY / MAX_2_DISTINCT_TICKETS_PER_RACE / NO_THRESHOLD_RELAXATION / NO_NEW_CANDIDATE / NO_STAKE_CHANGE / NO_AUTO_PURCHASE`
