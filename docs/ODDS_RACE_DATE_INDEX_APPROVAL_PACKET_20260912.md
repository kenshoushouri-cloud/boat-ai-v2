# `idx_v2_odds_race_date` approval packet

Date: 2026-09-12 JST
Status: **RESEARCH ONLY / NO DROP AUTHORIZED**
Parent research: PR #336 (`research/storage-retention-contract-20260912`)

## Purpose

This packet freezes the evidence and safety gates required before any future decision about removing `idx_v2_odds_race_date` from Production PostgreSQL. It is intentionally documentation-only. It does not authorize or execute any schema change, database write, backup operation, VACUUM, Railway setting change, model change, LINE change, or purchase action.

Current gate:

`RACE_DATE_INDEX_RESEARCH_CANDIDATE_ONLY / STATIC_DIRECT_CONSUMER_0 / INSTRUMENTATION_COUNTER_CONTAMINATION_KNOWN / FRESH_BACKUP_REQUIRED / EXPLICIT_PRODUCTION_APPROVAL_REQUIRED / NO_DROP_AUTHORIZED`

## 1. Current Production evidence

Read-only inventory from PR #336 identified:

- table: `public.v2_odds_trifecta`
- relation total: about `1.897 GB`
- table indexes total: about `929 MB`
- candidate index: `idx_v2_odds_race_date`
- candidate index size: `70,885,376` bytes (about `67.6 MiB`, commonly rounded to `70.9 MB` decimal)
- indexed column: `race_date`
- no constraint owns this index
- exact stored definition observed from PostgreSQL metadata:

```sql
CREATE INDEX idx_v2_odds_race_date
ON public.v2_odds_trifecta USING btree (race_date);
```

The large base-odds table itself is real historical data and is **not** a cleanup target under this packet.

## 2. Dependency evidence

### Repository workload

A pure static audit scans Python/SQL string constants without importing PostgreSQL, Railway, network, or subprocess clients.

Latest verified result at parent PR head `7d4d19bc1f211e8aa7938b6da0ec91647a9408ca`:

- SQL strings containing `v2_odds_trifecta`: `72`
- direct `v2_odds_trifecta.race_date` candidates: `0`
- qualified direct references: `0`
- unqualified direct WHERE references attributable to the odds table: `0`
- unit tests: `8/8 PASS`
- CI: `Storage Odds Race Date Static Audit` run #5 `SUCCESS`

The audit deliberately excludes `.github/scripts/storage_odds_index_readonly.py`, because that file is instrumentation whose purpose is to issue representative date-query EXPLAINs against the candidate index. Instrumentation is not a Production consumer.

Common repository patterns instead constrain dates through `v2_races.race_date` and join odds by `race_id`, or convert date windows to race-id ranges.

### Non-repository limitation

Static repository evidence cannot prove that no operator, ad-hoc SQL client, external tool, or future code uses `v2_odds_trifecta.race_date` directly. Therefore `0` repository consumers is supportive evidence only, not sufficient authorization to drop the index.

## 3. Index usage-counter interpretation

The earliest dedicated read-only index audit observed `idx_scan=0` for `idx_v2_odds_race_date`.

Later audits observed increasing scan counts, but earlier versions of the audit itself executed date-shaped queries such as `min/max(race_date)` or representative date predicates. Those probes can increment the index usage counters. Consequently:

- post-probe increases in `pg_stat_*` index scan counters are **not valid evidence of organic Production use**;
- the initial pre-probe zero remains useful historical context;
- future usage evidence must avoid self-contamination.

The corrected audit uses **static representative literals + `EXPLAIN` without `ANALYZE`**, with no data-sampling query used to choose parameters. It records:

`STORAGE_ODDS_INDEX_PLAN_SAMPLES=STATIC_EXPLAIN_ONLY_NO_DATA_SAMPLE`

Representative direct date predicates select the index when such a query is submitted. This proves the index can be useful for direct date-query shapes; it does not prove Production actually submits those shapes.

## 4. Why the index is only a candidate

Evidence in favor of possible removal:

1. approximately `70.9 MB` of physical index relation size;
2. no repository Production/research SQL consumer found that directly filters the odds table by its own `race_date` column;
3. no constraint ownership;
4. initial pre-instrumentation usage evidence was zero;
5. most known odds access is by `race_id`.

Evidence against immediate removal:

1. direct date-query shapes do benefit from the index;
2. repository static analysis cannot observe external/ad-hoc consumers;
3. current Production storage pressure alone does not justify an unreviewed schema mutation;
4. the currently visible backup is stale for a new schema-removal recovery gate;
5. a DROP is a Production schema change and requires explicit approval under the project policy.

Conclusion: **research candidate only; no Production change is authorized.**

## 5. Mandatory pre-change gates

All gates below must pass immediately before any future DROP request. Passing these gates still does not itself authorize the DROP.

### Gate A — fresh restore point

A fresh, restorable Production backup/restore point must exist and be independently verified after the latest meaningful Production writes and before the schema change.

The previously visible `Pre-Security-Patch Backup` was created on 2026-08-23 and is too old for this purpose.

Backup creation or restore testing is itself a Production operation and requires separate explicit approval.

### Gate B — current index identity

Read-only metadata must re-confirm immediately before change:

- exact index name: `idx_v2_odds_race_date`
- table: `public.v2_odds_trifecta`
- access method: btree
- key: `race_date`
- no constraint dependency
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

Absence of observed usage is not equivalent to proof of no external use.

### Gate E — explicit Production approval

The final operation must be presented separately and receive explicit user approval naming the Production schema change. Research PR approval, CI success, or this packet does not satisfy this gate.

## 6. Proposed change — reference only, not authorized

If and only if all gates pass and explicit Production approval is subsequently given, the contemplated schema action is removal of this single standalone index only.

Reference statement:

```sql
DROP INDEX public.idx_v2_odds_race_date;
```

**Do not execute this statement from research CI, from this PR, or without the separate Production approval.**

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

For a live Production rollback, lock behavior and build strategy must be reviewed at execution time. If `CREATE INDEX CONCURRENTLY` is selected to reduce blocking, that is still a separate Production schema operation and must be explicitly approved; it must not be silently substituted by automation.

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

- `DROP INDEX`;
- `DELETE` / `UPDATE` / row cleanup;
- `VACUUM` / `VACUUM FULL` / `ANALYZE`;
- backup creation or restore;
- Railway service/Variable/Cron/volume changes;
- `learning_all` pause or behavior changes;
- model coefficients/threshold changes;
- LINE behavior changes;
- Forward persistence changes;
- purchase behavior.

Final status:

**`NO_DROP_AUTHORIZED`**
