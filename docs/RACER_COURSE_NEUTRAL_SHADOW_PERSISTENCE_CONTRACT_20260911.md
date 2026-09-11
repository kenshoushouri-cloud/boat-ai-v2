# Racer Course neutral Forward shadow persistence contract — 2026-09-11

Status: `RESEARCH_ONLY / NO_SCHEMA_CREATED / NO_WRITES / NO_RAILWAY_CHANGE`

This document defines the persistence boundary for a future prospective Racer Course neutral-missing shadow. It does not create a table, deploy a service, configure a Cron, modify Production predictions, or connect to LINE/purchase behavior.

## Frozen model contract

- BASE: current v24 PRE raw strength, unchanged.
- Course coefficient: fixed `0.50`.
- Probability temperature: fixed `2.20`.
- Course evidence: exact `(race_date, racer_number, course=lane)` only.
- timing: evidence `created_at <= 08:15 JST` and strictly before race deadline.
- missing/unusable lane: `course_z=0`; BASE raw must remain exactly unchanged at that lane before persistence.
- fewer than two usable Course observations or near-zero observed SD: no Course adjustment.
- no later snapshot repair, subgroup tuning, odds, payout, ROI or result data in the forward write path.

## Proposed shadow namespace

Reserved research table name: `v2_racer_course_neutral_shadow`.

This table does **not** exist as a result of this PR.

Proposed immutable primary key:

`(race_id, shadow_version)`

Proposed version:

`course-neutral-missing-v1`

Proposed write policy:

`FIRST_WRITE_WINS_DO_NOTHING`

No UPDATE path should exist. A repeated natural run for the same `(race_id, shadow_version)` must not mutate an earlier prospective record.

## Required persisted evidence

One prospective row per race should retain enough evidence to independently audit what was known at write time:

- `race_id`, `race_date`, `shadow_version`, `base_version`;
- fixed `course_coef=0.50`, `prob_temp=2.20`;
- six racer numbers in lane order;
- six-lane usable mask;
- six Course Top3 values, with NULL for unavailable lanes;
- six unavailability reasons;
- BASE raw six-vector;
- Course z six-vector;
- adjusted raw six-vector;
- compact ticket-order version `canonical-permutations-1to6-v1`;
- BASE trifecta 120-vector;
- adjusted trifecta 120-vector;
- timezone-aware `observed_at` representing the prospective decision observation time.

The 120 ticket strings themselves should **not** be stored on every row. Their order is deterministic from the ticket-order version. This avoids repeating the same labels for every race.

The persistence adapter must reject malformed vectors, non-finite values, non-normalized probability vectors, post-08:15 observations, at/after-deadline observations, and any unavailable lane whose Course z is non-zero or whose adjusted raw differs from BASE.

## Compact storage direction

If a real schema is later approved, use typed arrays rather than JSONB for the fixed-size numeric vectors. A compact direction is:

- `integer[]` racer numbers;
- `boolean[]` usable mask;
- `real[]` Course Top3 / BASE raw / Course z / adjusted raw;
- compact reason codes or a six-element reason representation;
- `real[]` BASE trifecta / adjusted trifecta, each cardinality 120;
- scalar version/timing metadata.

A rough payload-only estimate for this compact layout is about **1.37 KB per race before PostgreSQL row/index overhead**. At 144 races/day this is about **0.19 MB/day**, **5.6 MB/30 days**, or **68.5 MB/year** before DB overhead/indexes. Even allowing substantial row/index overhead, this is much smaller than storing repeated ticket labels or JSON documents.

This estimate is planning evidence only. Before creating any schema, actual PostgreSQL type/row-size measurements and current volume headroom must be reviewed again.

## Integration boundary

`research/racer_course_neutral_shadow_integration.py` is deliberately pure. It prepares a validated immutable row contract but imports no database/network client and issues no SQL.

Before a real Forward shadow can be activated, a separate review must explicitly approve:

1. schema creation;
2. a dedicated writer implementation;
3. runtime/service location;
4. Cron time;
5. Railway variables/configuration;
6. storage impact on the 5 GB Boat PostgreSQL volume;
7. prospective natural-run acceptance criteria.

Those actions are outside this research PR.

## Forbidden coupling

The future shadow writer must not:

- overwrite current v24/FINAL predictions;
- feed BUY/WATCH/SKIP;
- feed LINE notifications;
- perform or trigger purchases;
- read race results before freezing the prospective row;
- read payout/ROI to decide whether to write;
- tune coefficient or thresholds online;
- backfill a missed natural prospective row with later information and count it as Forward evidence.

## Current gate

Historical/post-study evidence and pure contracts support an implementation review only.

`COURSE_NEUTRAL_SHADOW_PERSISTENCE_CONTRACT_DEFINED / COMPACT_STORAGE_ESTIMATED / REAL_WRITE_PATH_NOT_AUTHORIZED / BLOCK_NO_PRODUCTION_CHANGE`
