# `v2_odds_trifecta` index capacity review — 2026-09-12

Research-only. No index, constraint, table, Production DB data, Railway setting, Cron, model, LINE, or service was changed.

## Why this table matters

`v2_odds_trifecta` is the largest relation in the Production PostgreSQL database. Integrated read-only audit run #106 observed:

- total relation: `1,898,651,648` bytes
- heap: `968,269,824` bytes
- indexes: `930,078,720` bytes
- exact rows: `7,921,896`
- database share: about 49%

The historical rows themselves are real model/research data and are not classified as a cleanup target. The index footprint is therefore a separate capacity question.

## Read-only index inventory

The integrated audit runs with PostgreSQL default-transaction read-only mode, `temp_file_limit=65536`, static rejection of mutation primitives, and PR-level serialization of the heavy audit workflow.

| Index | Bytes | Role | `idx_scan` | Observation |
|---|---:|---|---:|---|
| `ux_v2_odds_trifecta_race_ticket` | 547,282,944 | unique `(race_id,ticket)` | 372,429 | heavily used; identity/query path |
| `v2_odds_trifecta_pkey` | 202,407,936 | primary key `(id)` | 0 | zero read scans, but primary-key schema semantics; preserve |
| `idx_v2_odds_race_id` | 109,445,120 | btree `(race_id)` | 19,587 | actively used despite structural prefix overlap |
| `idx_v2_odds_race_date` | 70,942,720 | btree `(race_date)` | **9** | low but non-zero observed use; no longer classifiable as zero-use |

`pg_stat_database.stats_reset` remains `NULL`. The counters are retained Production statistics, not proof of every external/ad-hoc workload. Importantly, the race-date index changed from an earlier observed zero-scan state to **9 scans / 8 tuples read / 8 tuples fetched**. Any deletion case must therefore explain those scans before the index can be called redundant or unused.

## `idx_v2_odds_race_id` must not be treated as redundant

Structurally, `(race_id)` is a left prefix of the unique `(race_id,ticket)` btree. That makes it superficially look redundant.

Production statistics and static planner checks reject that conclusion:

- `idx_v2_odds_race_id`: `19,587` scans
- tuples read: `59,464,503`
- tuples fetched: `45,488,874`
- representative `race_id = ?` + `ORDER BY race_id,ticket` query: planner selected `idx_v2_odds_race_id`
- representative `race_id = ?` count query: planner selected `idx_v2_odds_race_id`
- broad race-id range + ticket ordering: planner selected the composite unique index

The smaller single-column index and the larger composite index are serving different planner/cost cases. No DROP candidate is proposed for `idx_v2_odds_race_id`.

## `idx_v2_odds_race_date` — low use, not zero use

The race-date index is about **70.9 MB** and currently records:

- `idx_scan=9`
- `idx_tup_read=8`
- `idx_tup_fetch=8`
- valid/ready/live = true
- no constraint ownership

Static `EXPLAIN (FORMAT JSON)` checks, without `ANALYZE`, confirm that direct predicates on `v2_odds_trifecta.race_date` are planner-eligible and select this index for the tested shapes:

- direct race-date equality count
- direct race-date equality row retrieval
- direct race-date range count

These EXPLAIN-only probes do not intentionally execute the SELECT body and are not used as evidence that the index has runtime demand. The non-zero `pg_stat_user_indexes` counter instead means some executed workload has used the index since statistics began accumulating.

A bounded repository audit previously found that common owned code paths constrain `v2_races.race_date` and then reach odds through `race_id`, or convert date ranges into race-id ranges. The pure static consumer audit remains useful, but the new non-zero runtime counter means the stronger claim “unused” is no longer valid. Attribution of the 9 scans is now a required pre-drop gate.

Exact recreation DDL captured from live `pg_get_indexdef`:

```sql
CREATE INDEX idx_v2_odds_race_date
ON public.v2_odds_trifecta USING btree (race_date);
```

### Current classification

`idx_v2_odds_race_date` is classified as:

**`LOW_USAGE_SCHEMA_RESEARCH_CANDIDATE / NONZERO_RUNTIME_USE / NOT_AUTHORIZED_FOR_DROP`**

Reasons it is not approved as removable:

1. the index now has observed runtime scans, so their source must be attributed;
2. index statistics do not capture all workload intent or future/ad-hoc dependencies;
3. a DROP is a Production schema change;
4. rollback/recreation on a ~7.9M-row table has build-time, I/O, CPU and WAL risk;
5. capacity pressure alone is not sufficient reason to remove an index without a bounded dependency/performance review;
6. a fresh recovery point is still unresolved.

## Primary key index

`v2_odds_trifecta_pkey` is about **202.4 MB** and currently shows zero index scans. This is much larger than the race-date index, but it backs the table primary key.

Zero read scans do not make a primary key expendable. It carries schema/identity guarantees and may be relied on by tooling or future relationships even when repository queries use `(race_id,ticket)` instead. Removing or redesigning it would be a larger data-model decision and is explicitly **not** proposed as a capacity cleanup step.

## Physical-capacity caveat

Unlike deleting table rows, dropping an index normally removes a separate index relation rather than merely marking heap tuples reusable. Therefore an approved future index drop could be a more direct physical-capacity lever than ordinary DELETE/VACUUM.

That does **not** authorize the action or guarantee the exact Railway dashboard reduction. WAL, filesystem accounting, concurrent activity and follow-on maintenance can affect observed volume usage.

## PostgreSQL 18 execution constraints for any future approved change

If a future review eventually proves the non-constraint race-date index removable, the live-system execution candidate should be assessed around `DROP INDEX CONCURRENTLY`, not an ordinary blocking DROP.

PostgreSQL 18 documents that a normal `DROP INDEX` takes an `ACCESS EXCLUSIVE` table lock, while `CONCURRENTLY` avoids blocking ordinary SELECT/INSERT/UPDATE/DELETE and waits for conflicting transactions. `DROP INDEX CONCURRENTLY` has important restrictions: one index per command, no `CASCADE`, it cannot remove an index that supports a UNIQUE or PRIMARY KEY constraint, it cannot be run inside a transaction block, and it is not available for indexes on partitioned tables.

This index currently has no constraint ownership, but that fact must be rechecked immediately before any approved operation. A future recreation/rebuild plan should likewise consider `CREATE INDEX CONCURRENTLY`/`REINDEX CONCURRENTLY` semantics rather than assuming a blocking rebuild is acceptable; concurrent rebuilds trade lower write blocking for extra scans, resource use and longer execution.

No DROP/REINDEX/CREATE command is authorized by this research document.

## Safest future validation sequence for the race-date index

Before any Production drop request:

1. attribute the current 9 scans using repository/workflow/runtime evidence and determine whether they are recurring;
2. re-read current index counters immediately before the proposal;
3. inventory all constraints/dependencies and confirm the index is still non-constraint, valid, ready and live;
4. run static read-only `EXPLAIN` comparisons for repository-owned query shapes, including direct race-date controls;
5. confirm repository code and scheduled Production services have no required direct odds-table race-date workload;
6. freeze exact recreation DDL and a rollback/rebuild procedure;
7. estimate build/drop resource risk and identify an execution window;
8. close the fresh restorable recovery-point gate;
9. request a **separate explicit approval** for the Production schema change;
10. if approved, execute only the specifically approved index operation and verify DB health, planner behavior and physical disk afterward; do not bundle DELETE/VACUUM or other cleanup into the same approval.

## Current decision

`ODDS_TABLE_INDEX_BYTES_930078720 / RACE_TICKET_UNIQUE_HEAVILY_USED / RACE_ID_INDEX_109MB_ACTIVE_AND_PLANNER_SELECTED / RACE_ID_DROP_BLOCKED / PKEY_202MB_ZERO_READ_SCANS_BUT_SCHEMA_SEMANTIC_PRESERVE / RACE_DATE_INDEX_70_9MB_SCAN_COUNT_9 / RACE_DATE_RUNTIME_ATTRIBUTION_REQUIRED / RACE_DATE_INDEX_LOW_USAGE_RESEARCH_CANDIDATE_ONLY / DROP_CONCURRENTLY_REVIEW_IF_EVER_APPROVED / FRESH_RECOVERY_POINT_OPEN / NO_DROP_INDEX / NO_REINDEX / NO_SCHEMA_CHANGE / NO_PRODUCTION_CHANGE`
