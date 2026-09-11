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

### Latest read-only Boat PostgreSQL capacity snapshot

A read-only Railway metrics check on 2026-09-11 found `postgres-recovery` at approximately:

- disk: `4.1399 GB / 5 GB` used, about `0.86 GB` nominal headroom;
- disk utilization: about `82.8%`;
- memory current: about `0.50 GB`, with a recent maximum about `1.30 GB`;
- CPU: low at the observation point.

This snapshot does **not** authorize schema creation. Capacity must be re-measured immediately before any approved schema/write change, and secondary-sport datasets must remain outside this Boat PostgreSQL volume.

## Predeclared prospective natural-shadow acceptance criteria

These criteria are defined before any real Course-neutral shadow rows exist. They are intended only to judge whether a future approved shadow writer is technically trustworthy; passing them must not automatically promote the model into Production decisions.

A future prospective validation should report, for every natural eligible race day:

1. **Timing integrity:** every persisted row has `observed_at <= 08:15 JST` and `observed_at < race deadline`; any violation makes the day fail-closed.
2. **Immutability:** zero rows with later mutation; repeated attempts for the same `(race_id, shadow_version)` leave the first row unchanged.
3. **Vector integrity:** exactly six lane entries and exactly 120 canonical trifecta probabilities for both BASE and adjusted vectors; all values finite and each probability vector normalized.
4. **Neutral-missing integrity:** every unusable lane has `course_z=0` and `adjusted_raw == base_raw` exactly within the frozen numeric tolerance; no later snapshot may repair a missing lane.
5. **Identity integrity:** racer/lane/date identity matches the race card exactly; no wrong-date, wrong-course or cross-race evidence is accepted.
6. **Coverage accounting:** report target races, persisted races, blocked races and blocked reasons separately. Coverage is evidence, not a reason to relax timing or neutrality gates.
7. **Natural-operation evidence:** collect at least **5 eligible natural race days** without manual rerun/backfill before implementation reliability is reviewed. A missing or failed day is reported as-is and is not repaired for Forward credit.
8. **Storage evidence:** measure actual row/index growth during the approved shadow period and compare it with the planning estimate before any extension of retention.
9. **Isolation:** the shadow path must have no LINE, purchase, BUY/WATCH/SKIP, current prediction overwrite or result-conditioned write dependency.
10. **No auto-promotion:** even a clean 5-day technical run only permits a separate review. Predictive/ROI evaluation requires later realized results and a separately frozen analysis plan; coefficients and thresholds remain unchanged.

The 5-day requirement is a minimum technical reliability sample, not a statistical efficacy claim.

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

`COURSE_NEUTRAL_SHADOW_PERSISTENCE_CONTRACT_DEFINED / PROSPECTIVE_ACCEPTANCE_CRITERIA_PREDECLARED / COMPACT_STORAGE_ESTIMATED / CAPACITY_RECHECK_RECORDED / REAL_WRITE_PATH_NOT_AUTHORIZED / BLOCK_NO_PRODUCTION_CHANGE`
