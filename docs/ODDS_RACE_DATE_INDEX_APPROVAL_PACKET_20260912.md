# `idx_v2_odds_race_date` approval packet

Date: 2026-09-12 JST
Status: **RESEARCH ONLY / NO DROP AUTHORIZED**
Parent research: PR #336 (`research/storage-retention-contract-20260912`)

## Purpose

This packet freezes the evidence and safety gates required before any future decision about removing `idx_v2_odds_race_date` from Production PostgreSQL. It is intentionally documentation-only. It does not authorize or execute any schema change, database write, backup operation, VACUUM, Railway setting change, model change, LINE change, or purchase action.

Current gate:

`RACE_DATE_INDEX_RESEARCH_CANDIDATE_ONLY / STATIC_DIRECT_CONSUMER_0 / INITIAL_SCAN_BASELINE_0 / RESEARCH_COUNTER_CONTAMINATION_KNOWN / FRESH_BACKUP_REQUIRED / EXPLICIT_PRODUCTION_APPROVAL_REQUIRED / NO_DROP_AUTHORIZED`

## 1. Current Production evidence

Latest integrated read-only inventory from parent PR #336 identified:

- table: `public.v2_odds_trifecta`
- relation total: `1,898,651,648` bytes
- table indexes total: `930,078,720` bytes
- exact rows: `7,921,896`
- candidate index: `idx_v2_odds_race_date`
- candidate index size: `70,942,720` bytes (about `67.7 MiB`, commonly rounded to `70.9 MB` decimal)
- indexed column: `race_date`
- no constraint owns this index
- current cumulative catalog counter: `idx_scan=9`, `idx_tup_read=8`, `idx_tup_fetch=8`
- exact stored definition observed from PostgreSQL metadata:

```sql
CREATE INDEX idx_v2_odds_race_date
ON public.v2_odds_trifecta USING btree (race_date);
```

The large base-odds table itself is real historical data and is **not** a cleanup target under this packet.

## 2. Dependency evidence

### Repository workload

A pure static audit scans Python/SQL string constants without importing PostgreSQL, Railway, network, or subprocess clients.

Latest verified result:

- SQL strings containing an actual `v2_odds_trifecta` FROM/JOIN: `72`
- direct `v2_odds_trifecta.race_date` candidates: `0`
- qualified direct references: `0`
- unqualified direct WHERE references attributable to the odds table: `0`
- unit tests: `8/8 PASS`
- isolation: PASS

The audit deliberately excludes `.github/scripts/storage_odds_index_readonly.py`, because that file is instrumentation whose purpose is to issue representative date-query EXPLAINs against the candidate index. Instrumentation is not a Production consumer.

Common repository patterns instead constrain dates through `v2_races.race_date` and join odds by `race_id`, or convert date windows to race-id ranges.

### Non-repository limitation

Static repository evidence cannot prove that no operator, ad-hoc SQL client, external tool, or future code uses `v2_odds_trifecta.race_date` directly. Therefore `0` repository consumers is supportive evidence only, not sufficient authorization to drop the index.

## 3. Index usage-counter interpretation

The cumulative `idx_scan=9` must **not** be interpreted as nine organic Production-runtime uses. The research process itself is known to have incremented this counter.

Confirmed chronology:

1. the earliest dedicated read-only index audit observed **`idx_scan=0`** before its own diagnostic date probes accumulated;
2. early versions of the index audit executed `min/max(race_date)` and representative direct date predicates to choose sample values. Later runs observed **2 then 6 scans**. PR #336 explicitly identified this as self-contamination rather than Production demand;
3. commit `ef626c91920ef189f704ad2be59ff27d1e4c8a9d` removed that behavior and changed the planner evidence to static literals with `EXPLAIN` only;
4. a separate early current-growth script initially treated `v2_odds_trifecta.race_date` as a usable date key and executed a direct bounded predicate. `Storage Current Growth Readonly` run `34674650540` executed that query once and returned `rows7:0 / active_dates:0` for the odds table. The script was corrected in commit `5a74fb58cb76180e241c4e43ce67ba8cdb4bea51` to resolve dates through `v2_races`, and the one-shot workflow was subsequently retired;
5. the current integrated index audit reads the usage counter but no longer intentionally executes a race-date data scan. Its date planner controls use static literals + `EXPLAIN` without `ANALYZE`.

Consequences:

- the initial pre-instrumentation zero remains important historical context;
- the current cumulative nine scans are **research/audit-contaminated** and are not valid evidence of steady Production demand;
- not every individual increment can be reconstructed from `pg_stat_user_indexes` after the fact, so this packet does not overclaim that all nine are explained;
- future usage evidence must avoid self-contamination and should rely on a deliberately frozen clean observation strategy if runtime-use evidence is needed.

Representative direct date predicates do select the index when such a query is submitted. This proves the index can be useful for direct date-query shapes; it does not prove Production actually submits those shapes.

## 4. Why the index is only a candidate

Evidence in favor of possible removal:

1. approximately `70.9 MB` of physical index relation size;
2. pure static audit finds `0` direct odds-table `race_date` consumers across 72 checked-in odds SQL strings;
3. no constraint ownership;
4. initial pre-instrumentation usage evidence was zero;
5. much of the later cumulative counter is known to be generated by research diagnostics;
6. most known operational odds access is by `race_id`.

Evidence against immediate removal:

1. direct date-query shapes do benefit from the index if submitted;
2. repository static analysis cannot observe external/ad-hoc consumers;
3. current Production storage pressure alone does not justify an unreviewed schema mutation;
4. the currently visible backup is stale for a new schema-removal recovery gate;
5. a DROP is a Production schema change and requires explicit approval under the project policy;
6. recreate/rollback on a ~7.9M-row table has CPU/I/O/WAL and duration risk.

Conclusion: **research candidate only; no Production change is authorized.**

## 5. Mandatory pre-change gates

All gates below must pass immediately before any future DROP request. Passing these gates still does not itself authorize the DROP.

### Gate A — fresh restore point

A fresh, restorable Production backup/restore point must exist and be independently verified after the latest meaningful Production writes and before the schema change.

The visible `Pre-Security-Patch Backup` was created on 2026-08-23 and is too old for this purpose.

Current Railway recovery research shows the simplest manual-volume-backup path is not reliable at the present Hobby 5 GB volume usage because Railway documents manual backups as limited to 50% of volume capacity. The least image-invasive native candidate is a Daily volume-backup schedule, but changing that schedule is itself a Railway Production setting change and requires separate explicit approval. PITR is also not currently enabled and has separate digest/tag compatibility questions.

Backup/schedule creation or restore testing is itself a Production operation and is not authorized by this packet.

### Gate B — current index identity

Read-only metadata must re-confirm immediately before change:

- exact index name: `idx_v2_odds_race_date`
- table: `public.v2_odds_trifecta`
- access method: btree
- key: `race_date`
- no constraint dependency
- valid / ready / live state
- no unexpected predicate / INCLUDE column / expression change

If definition drift is detected, **abort** and prepare a new packet.

### Gate C — current static dependency audit

Re-run the pure static repository audit against the then-current target commit. Required result:

`ODDS_RACE_DATE_DIRECT_CANDIDATES=0`

Any direct consumer result blocks the removal request until separately reviewed.

### Gate D — workload evidence without self-contamination

Use read-only, non-mutating evidence only. Do not run `ANALYZE`, do not use `EXPLAIN ANALYZE`, and do not issue data-sampling queries solely to manufacture date-index scans.

At minimum capture:

- current index size and definition;
- current relation size;
- current query-plan samples using fixed representative literals;
- any available organic query-statistics evidence if a trusted non-self-contaminating source exists.

The current cumulative `idx_scan=9` must be labeled contaminated and must not be used as a clean runtime baseline. Absence of observed usage is not equivalent to proof of no external use.

### Gate E — explicit Production approval

The final operation must be presented separately and receive explicit user approval naming the Production schema change. Research PR approval, CI success, or this packet does not satisfy this gate.

## 6. Proposed change — reference only, not authorized

If and only if all gates pass and explicit Production approval is subsequently given, the contemplated schema action is removal of this single standalone index only.

For a live Production table, the execution candidate should be reviewed around:

```sql
DROP INDEX CONCURRENTLY public.idx_v2_odds_race_date;
```

rather than silently defaulting to a normal blocking DROP. PostgreSQL documents that normal `DROP INDEX` takes an `ACCESS EXCLUSIVE` table lock, whereas `CONCURRENTLY` avoids blocking ordinary SELECT/INSERT/UPDATE/DELETE while it waits for conflicting transactions. `DROP INDEX CONCURRENTLY` is restricted: one index per command, no `CASCADE`, cannot remove an index supporting a UNIQUE/PRIMARY KEY constraint, cannot run inside a transaction block, and is not available for indexes on partitioned tables.

**This is reference material only. Do not execute this statement from research CI, from this PR, or without separate explicit Production approval.**

No table rows should be deleted. No other index should be removed. In particular:

- preserve unique `(race_id, ticket)` index;
- preserve primary key `(id)`;
- preserve `idx_v2_odds_race_id` because planner/use evidence shows it is active and useful.

## 7. Rollback / recreation contract

The index can be semantically recreated from the captured metadata as:

```sql
CREATE INDEX idx_v2_odds_race_date
ON public.v2_odds_trifecta USING btree (race_date);
```

For a live Production rollback, lock behavior and build strategy must be reviewed at execution time. If `CREATE INDEX CONCURRENTLY` or `REINDEX CONCURRENTLY` is selected to reduce blocking, that is still a separate Production schema operation and must be explicitly approved; it must not be silently substituted by automation. Concurrent build/rebuild reduces ordinary write blocking but costs additional scans/resources and may take longer.

Rollback must be triggered if, after an approved removal, any of the following is observed and reasonably attributable to the missing index:

- material regression in known date-scoped odds queries;
- new/current Production code requiring direct `v2_odds_trifecta.race_date` filtering;
- unacceptable query latency or resource usage;
- operational errors caused by an external consumer assumption.

## 8. Post-change verification contract

Only after an explicitly approved change, verify read-only:

1. the candidate index is absent and all protected indexes remain present;
2. `v2_odds_trifecta` row count/content is unchanged by the index operation;
3. representative current Production query shapes still receive acceptable plans;
4. cron/collector/decision/notifier health remains normal;
5. Railway volume and PostgreSQL relation sizes are measured as observations, not promised reclaim amounts.

Dropping a standalone index normally removes that index relation, but this packet makes **no guarantee** that Railway's displayed volume usage will decrease by exactly the index size or immediately.

## 9. Abort conditions

Abort before any schema mutation if any of the following is true:

- no fresh recovery point;
- index definition differs from this packet;
- static audit finds a direct consumer;
- protected index identities differ;
- Production is under abnormal load or database health is degraded;
- approval wording is ambiguous or does not explicitly cover the DROP;
- rollback/recreation path has not been reviewed for the current PostgreSQL/Railway state.

## 10. Explicit non-actions

This packet does **not** authorize:

- `DROP INDEX` / `CREATE INDEX` / `REINDEX`;
- `DELETE` / `UPDATE` / row cleanup;
- `VACUUM` / `VACUUM FULL` / `ANALYZE`;
- backup creation or restore;
- Railway service/Variable/Cron/backup-schedule/volume changes;
- `learning_all` pause or behavior changes;
- model coefficients/threshold changes;
- LINE behavior changes;
- Forward persistence changes;
- purchase behavior.

Final status:

**`INITIAL_SCAN_BASELINE_0 / CURRENT_COUNTER_9_RESEARCH_CONTAMINATED / STATIC_DIRECT_CONSUMERS_0 / FRESH_RECOVERY_POINT_OPEN / EXPLICIT_PRODUCTION_APPROVAL_REQUIRED / NO_DROP_AUTHORIZED`**
