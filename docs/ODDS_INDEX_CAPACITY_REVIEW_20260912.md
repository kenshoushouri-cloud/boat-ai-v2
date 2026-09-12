# `v2_odds_trifecta` index capacity review — 2026-09-12

Research-only. No index, constraint, table, Production DB data, Railway setting, Cron, model, LINE, or service was changed.

## Why this table matters

`v2_odds_trifecta` is the largest relation in the Production PostgreSQL database:

- total relation: `1,896,914,944` bytes
- heap: `967,376,896` bytes
- indexes: `929,234,944` bytes
- exact rows: `7,914,324`
- database share: about 49%

The historical rows themselves are real model/research data and are not classified as a cleanup target. The index footprint is therefore a separate capacity question.

## Read-only index inventory

The dedicated audit runs with PostgreSQL default-transaction read-only mode and static rejection of mutation primitives.

| Index | Bytes | Role | `idx_scan` | Observation |
|---|---:|---|---:|---|
| `ux_v2_odds_trifecta_race_ticket` | 546,783,232 | unique `(race_id,ticket)` | 363,807 | heavily used; identity constraint/query path |
| `v2_odds_trifecta_pkey` | 202,227,712 | primary key `(id)` | 0 | zero read scans, but primary-key schema semantics; not a routine cleanup candidate |
| `idx_v2_odds_race_id` | 109,338,624 | btree `(race_id)` | 3,377 | actively used despite structural prefix overlap |
| `idx_v2_odds_race_date` | 70,885,376 | btree `(race_date)` | 0 | no observed scans; strongest research candidate for further review |

`pg_stat_database.stats_reset` was `NULL` in this audit. The zero counters are evidence of no recorded use in the currently retained statistics, not a proof that no possible external/ad-hoc query can benefit from the index.

## `idx_v2_odds_race_id` must not be treated as redundant

Structurally, `(race_id)` is a left prefix of the unique `(race_id,ticket)` btree. That makes it superficially look redundant.

However, Production statistics and planner checks reject that simplistic conclusion:

- `idx_v2_odds_race_id`: `3,377` scans
- tuples read: `55,664,230`
- tuples fetched: `42,552,148`
- representative `race_id = ?` + `ORDER BY race_id,ticket` query: planner selected `idx_v2_odds_race_id`
- representative `race_id = ?` count query: planner selected `idx_v2_odds_race_id`
- broad race-id range + ticket ordering: planner selected the composite unique index

The smaller single-column index and the larger composite index are therefore serving different cost/planner cases in current Production behavior. No DROP candidate is proposed for `idx_v2_odds_race_id`.

## `idx_v2_odds_race_date` is different

The race-date index is about **70.9 MB** and recorded:

- `idx_scan=0`
- `idx_tup_read=0`
- `idx_tup_fetch=0`

A bounded repository search found no reference to the literal index name. Common code paths that constrain dates typically filter `v2_races.race_date` and then join or query `v2_odds_trifecta` by `race_id`; examples include daily data-preparation quality checks and backtest readiness checks. Another common family converts date ranges into race-id ranges and queries the odds table by `race_id`.

A bounded search for `o.race_date` on `v2_odds_trifecta` returned no result. This supports, but does not prove, that the direct odds-table race-date index is legacy/unused by repository-owned workloads.

### Current classification

`idx_v2_odds_race_date` is classified as:

**`SCHEMA_CHANGE_RESEARCH_CANDIDATE / NOT_AUTHORIZED_FOR_DROP`**

Reasons it is not yet approved as removable:

1. index statistics do not capture every hypothetical external/ad-hoc workload;
2. a DROP is a Production schema change;
3. rollback/recreation cost on a ~7.9M-row table must be planned;
4. capacity pressure alone is not sufficient reason to remove an index without a bounded performance comparison.

## Primary key index

`v2_odds_trifecta_pkey` is about **202.2 MB** and currently shows zero index scans. This is much larger than the race-date index, but it backs the table primary key.

Zero read scans do not make a primary key expendable. It can carry identity/schema guarantees and may be relied on by tooling or future relationships even when repository queries use `(race_id,ticket)` instead. Removing or redesigning it would be a larger schema/data-model decision and is explicitly **not** proposed as a capacity cleanup step.

## Physical-capacity caveat

Unlike deleting table rows, dropping an index would normally remove a separate index relation rather than merely marking heap tuples reusable. Therefore an approved future index drop could be a more direct physical-capacity lever than ordinary DELETE/VACUUM.

That does **not** authorize the action or guarantee the exact Railway dashboard reduction; filesystem/volume accounting and WAL/temporary effects still need to be considered.

## Safest future validation sequence for the race-date index

Before any Production drop request:

1. verify current index counters again immediately before the proposal;
2. inventory all constraints/dependencies on the index/table;
3. run read-only `EXPLAIN` comparisons for repository-owned query shapes, including direct race-date predicates as a negative/control case;
4. confirm repository code still has no direct odds-table race-date workload that depends on it;
5. define exact recreation DDL and expected build time/resource risk;
6. require a fresh restorable backup/restore point if the wider cleanup plan requires one;
7. request separate explicit approval for the Production schema change.

## Current decision

`ODDS_TABLE_INDEX_BYTES_929234944 / RACE_TICKET_UNIQUE_HEAVILY_USED / RACE_ID_INDEX_109MB_ACTIVE_AND_PLANNER_SELECTED / RACE_ID_DROP_BLOCKED / PKEY_202MB_ZERO_READ_SCANS_BUT_SCHEMA_SEMANTIC_PRESERVE / RACE_DATE_INDEX_70_9MB_ZERO_SCANS / REPO_OWNED_DIRECT_RACE_DATE_DEPENDENCY_NOT_FOUND_IN_BOUNDED_SEARCH / RACE_DATE_INDEX_RESEARCH_CANDIDATE_ONLY / NO_DROP_INDEX / NO_SCHEMA_CHANGE / NO_PRODUCTION_CHANGE`
