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
| `idx_v2_odds_race_date` | 70,942,720 | btree `(race_date)` | **9** | counter is known to be research-audit contaminated; not valid as steady Production-demand evidence |

`pg_stat_database.stats_reset` remains `NULL`, so the counters accumulate across the retained statistics lifetime. For the race-date index, however, the current count must not be interpreted naively: this research branch itself executed direct race-date probes before those probes were corrected.

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

## `idx_v2_odds_race_date` — initial zero baseline, later self-contaminated counter

The race-date index is about **70.9 MB**. The current catalog counter is:

- `idx_scan=9`
- `idx_tup_read=8`
- `idx_tup_fetch=8`
- valid/ready/live = true
- no constraint ownership

The important chronology is:

1. the dedicated read-only index audit initially observed **`idx_scan=0`** before its own race-date sampling probes had accumulated;
2. early versions of that audit executed a `min/max(race_date)` lookup to obtain planner sample values; later runs observed **2 then 6 scans**, and the PR explicitly recorded this as self-contamination rather than Production demand;
3. commit `ef626c91920ef189f704ad2be59ff27d1e4c8a9d` changed the audit to static literals for `EXPLAIN` and removed that data-sampling query;
4. a separate early current-growth audit initially treated `v2_odds_trifecta.race_date` as a usable date key and executed a direct bounded `WHERE race_date >= current_date - 7 AND race_date < current_date` query. Workflow run `34674650540` executed this query once and returned zero matching odds rows. The script was then corrected by commit `5a74fb58cb76180e241c4e43ce67ba8cdb4bea51` to resolve dates through `v2_races`, and that one-shot workflow was later retired;
5. current integrated audit now reads the counter but uses only static `EXPLAIN` literals for race-date planner tests, so it no longer intentionally adds a race-date data scan.

Therefore the current value 9 is **contaminated by known research/audit queries** and is not valid evidence that a steady Production runtime consumer requires this index. It is also not possible from the cumulative counter alone to attribute every one of the nine increments perfectly after the fact, so the safest statement is not “all 9 are explained,” but rather “the counter cannot be used as an uncontaminated Production-demand signal.”

### Static consumer evidence

A pure repository-static audit inspects checked-in Python SQL strings without PostgreSQL, Railway, or network access. Latest PASS evidence:

- SQL strings containing an actual `v2_odds_trifecta` FROM/JOIN: **72**
- direct `v2_odds_trifecta.race_date` candidates: **0**
- qualified direct (`o.race_date` / table-qualified): **0**
- unqualified WHERE `race_date` attributable to the odds relation: **0**
- synthetic/static tests: **8/8 PASS**
- the index instrumentation script itself is explicitly excluded from workload classification.

This is strong evidence that current checked-in repository code has no direct odds-table race-date predicate. It does not prove that an external/ad-hoc/non-repository consumer can never use the index.

Static `EXPLAIN (FORMAT JSON)`, without `ANALYZE`, confirms that if a direct odds-table race-date workload exists, the planner can select this index for equality/range shapes. Those EXPLAIN probes do not execute the SELECT body and are not counted as runtime-demand evidence.

Exact recreation DDL captured from live `pg_get_indexdef`:

```sql
CREATE INDEX idx_v2_odds_race_date
ON public.v2_odds_trifecta USING btree (race_date);
```

### Current classification

`idx_v2_odds_race_date` is classified as:

**`INITIAL_ZERO_BASELINE / RESEARCH_SELF_CONTAMINATED_COUNTER / STATIC_DIRECT_CONSUMERS_ZERO / SCHEMA_CHANGE_RESEARCH_CANDIDATE / NOT_AUTHORIZED_FOR_DROP`**

Reasons it is still not approved as removable:

1. the cumulative counter is contaminated and cannot establish a clean post-research observation window by itself;
2. static repository evidence does not cover unknown external/ad-hoc consumers;
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

1. establish a clean observation strategy that does not itself execute odds-table race-date predicates; do not use the contaminated cumulative counter as sole evidence;
2. re-read current index metadata immediately before the proposal and compare only against a deliberately frozen clean baseline if one exists;
3. inventory all constraints/dependencies and confirm the index is still non-constraint, valid, ready and live;
4. keep planner checks `EXPLAIN`-only with static literals and no `ANALYZE`/data-sampling probe;
5. confirm repository code and scheduled Production services have no required direct odds-table race-date workload;
6. freeze exact recreation DDL and a rollback/rebuild procedure;
7. estimate build/drop resource risk and identify an execution window;
8. close the fresh restorable recovery-point gate;
9. request a **separate explicit approval** for the Production schema change;
10. if approved, execute only the specifically approved index operation and verify DB health, planner behavior and physical disk afterward; do not bundle DELETE/VACUUM or other cleanup into the same approval.

## Current decision

`ODDS_TABLE_INDEX_BYTES_930078720 / RACE_TICKET_UNIQUE_HEAVILY_USED / RACE_ID_INDEX_109MB_ACTIVE_AND_PLANNER_SELECTED / RACE_ID_DROP_BLOCKED / PKEY_202MB_ZERO_READ_SCANS_BUT_SCHEMA_SEMANTIC_PRESERVE / RACE_DATE_INDEX_70_9MB_CURRENT_COUNTER_9 / INITIAL_RACE_DATE_SCAN_BASELINE_ZERO / COUNTER_RESEARCH_SELF_CONTAMINATED / STATIC_DIRECT_CONSUMERS_ZERO / RACE_DATE_INDEX_SCHEMA_RESEARCH_CANDIDATE_ONLY / DROP_CONCURRENTLY_REVIEW_IF_EVER_APPROVED / FRESH_RECOVERY_POINT_OPEN / NO_DROP_INDEX / NO_REINDEX / NO_SCHEMA_CHANGE / NO_PRODUCTION_CHANGE`
