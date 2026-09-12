# Storage Capacity Response Runbook — 2026-09-12

Status: **research / approval planning only**

This document does not authorize any Production mutation. In particular it does not authorize `DELETE`, `DROP INDEX`, `VACUUM`, `VACUUM FULL`, `ANALYZE`, backup creation/restore, Railway Production configuration changes, Cron/service changes, model/threshold changes, LINE changes, Forward persistence changes, or purchase behavior.

## 1. Current capacity snapshot

Read-only Railway metrics on 2026-09-12 JST:

- `postgres-recovery` volume current: about **4.183 GB / 5 GB**
- nominal volume headroom: about **0.817 GB**
- last 24h disk: min about 4.136 GB / max about 4.255 GB
- last 7d disk: min about 3.967 GB / max about 4.212 GB
- current memory about 2.41 GB / 8 GB; 24h max about 3.13 GB
- CPU is currently low

The repaired read-only DB-size workflow also reports PostgreSQL logical database size about **3700 MB**.

Railway volume usage and PostgreSQL logical database size are different measurements. WAL, temporary files, filesystem overhead, relation/index allocation, and other storage effects mean they must not be subtracted or projected as if they were the same metric.

No exact exhaustion date is asserted by this runbook.

## 2. Capacity-growth evidence

The dedicated seven-completed-day logical-growth audit measured about **15.31 MB/day** across the ten tracked tables. Largest tracked contributors were:

1. `v2_v24_motor2_forward_shadow`: about 6.06 MB/day logical payload
2. `v2_realtime_odds_snapshots`: about 5.03 MB/day
3. `v2_odds_trifecta`: about 1.72 MB/day
4. Racer Course stats: about 0.61 MB/day
5. realtime condition tables and Opponent Pressure: smaller contributors

This logical-growth sum is useful for attribution, but it is **not** a physical Railway-volume forecast.

The recent Railway disk range has sometimes moved faster than tracked logical tuple growth. Therefore capacity response must be based on fresh volume metrics immediately before any action.

## 3. Mandatory ordering rule

If Production capacity action becomes necessary, use this order:

1. **re-measure current disk and logical DB sizes**;
2. **confirm the exact candidate and its current dependencies**;
3. **create/verify a fresh restorable recovery point** — separate explicit approval required;
4. **perform only one approved mutation class at a time**;
5. **verify application health and capacity immediately afterward**;
6. **do not chain DELETE + VACUUM + DROP INDEX + archive cleanup into one approval**.

Every mutation class remains separately approvable and separately reversible where possible.

## 4. Candidate priority matrix

### Priority A — `idx_v2_odds_race_date` standalone index

Current evidence:

- index size about **70,885,376 bytes** (~67.6 MiB)
- earlier usage counter showed zero organic scans, but diagnostic probes contaminated later counters; counter evidence alone is not sufficient
- pure repository SQL static audit examined 72 odds-table SQL strings and found **0 direct Production/repository consumers of `v2_odds_trifecta.race_date`** after excluding the index diagnostic itself
- static audit tests: **8/8 PASS**
- common workloads filter `v2_races.race_date` and reach odds through `race_id`
- recreate definition is frozen in PR #341

Why it ranks first if a physical-capacity action is eventually required:

- standalone index removal can release a discrete physical relation rather than merely creating reusable free space inside a heap;
- no current repository consumer has been identified;
- rollback is conceptually simple because the exact recreate DDL is recorded.

Remaining mandatory gates:

- fresh backup/recovery point;
- fresh catalog metadata and exact index definition check;
- fresh static dependency audit;
- representative `EXPLAIN`/workload evidence without mutating Production data;
- explicit Production **schema-change / DROP INDEX approval**;
- post-change query/runtime monitoring;
- recreate immediately if any regression appears.

Current state: **NO_DROP_AUTHORIZED**.

Reference: PR #341 / `docs/ODDS_RACE_DATE_INDEX_APPROVAL_PACKET_20260912.md`.

### Priority B — Motor2 conservative retention candidate

Current evidence:

- protected-output invariance contract passes with zero diff for Performance, Robustness PRE/FINAL, and current PRE health
- conservative final/final candidate: **42,552 rows** at the frozen audit point
- protected intersection: zero
- recent-seven-day candidate estimate: **14,578 rows / 13,759,792 logical bytes**
- recent candidate growth about **1.97 MB/day logical payload**

Why it ranks below the standalone index:

- row deletion normally frees reusable PostgreSQL heap space but does not guarantee proportional Railway-volume shrink;
- physical shrink through rewrite/VACUUM FULL would be a separate higher-impact operation;
- candidate digest must be re-created immediately before execution because the table continues to grow.

Remaining mandatory gates:

- fresh backup/recovery point;
- current candidate digest;
- current zero-diff protected-output audit;
- explicit **DELETE approval** for an exact bounded candidate;
- separate explicit approval for any subsequent `VACUUM`/physical rewrite if considered.

Current state: **NO_DELETE_AUTHORIZED / NO_VACUUM_AUTHORIZED**.

### Priority C — completed `historical` realtime labels to external cold archive

Read-only inventory at the research point:

- historical weather: 63,468 rows / ~128.0 MB logical
- historical exhibition: 373,230 rows / ~76.6 MB logical
- historical race condition: 63,468 rows / ~128.5 MB logical
- historical racer condition: 380,808 rows / ~133.4 MB logical
- total: **880,974 rows / ~466.5 MB logical payload**
- historical series ended 2026-08-30 in the audited data, so this is a large **static footprint**, not the current daily-growth source

Dependency classification:

- no confirmed steady-state Production read path currently requires the completed historical-label rows to remain hot;
- research/OOS consumers still exist;
- maintenance/repair consumers still exist;
- optional Wave shadow historical dependency is currently default-off and not enabled in `cron-final-check` variables;
- scheduled Exhibition ST Forward has stored-historical replay explicitly disabled.

Why it is not an immediate delete candidate despite the larger byte count:

- these rows preserve research/replay/repair capability;
- an external archive destination and proven restore path do not yet exist;
- logical bytes are not a promise of equal Railway-volume reclaim.

Mandatory gates before any future cleanup:

- defined external archive target;
- lossless explicit-column format;
- immutable manifest, counts, schema/content digests;
- isolated restore-before-research proof;
- current runtime dependency recheck;
- fresh Production recovery point;
- exact bounded deletion inventory;
- separate explicit Production deletion approval.

Current state: **PRESERVE HOT / NO_DELETE_AUTHORIZED** until every archive/restore gate is closed.

Reference: PR #342 / `docs/HISTORICAL_LABEL_COLD_ARCHIVE_CONTRACT_20260912.md`.

### Priority D — completed `learning_all` rows to cold archive

Current research evidence:

- completed six-table `learning_all`: **451,818 rows / ~101.0 MB logical payload** at the audit point
- direct identity overlap with completed `final_ab`: 450,666 rows
- direct learning-only identities: 1,152
- hypothetical rows outside a seven-completed-day hot window: about **375,583 rows / ~84.0 MB logical payload**

Important semantic boundary:

- **live `learning_all` collection cannot simply be stopped** because final rows can use learning odds as their previous market sample through the cross-label previous-odds lookup;
- historical completed learning rows also have reproducibility/research value.

A pure archive manifest/restore contract exists, but no real archive destination or Production cleanup is authorized.

Current state: **PRESERVE / NO_DELETE_AUTHORIZED**.

### Priority E — odds-only `learning_all` mode

Research-only PR #337 defines a default-off mode that preserves learning odds cadence while skipping duplicated learning-side beforeinfo/non-odds writes.

Estimated prevention benefit:

- about **1,559 rows/day**
- about **0.62 MiB/day logical tuple payload**

This is a small capacity lever compared with the options above. Its stronger benefit would be reduced duplicate HTTP/parsing and non-odds write load.

Because activation changes Production runtime collection behavior and Railway variables, it remains a separate Production approval boundary.

Current state: **DEFAULT OFF / NO DEPLOY / NO RAILWAY CHANGE**.

## 5. Explicit preserve / blocked actions

The following are not capacity-cleanup candidates under current evidence:

- `v2_odds_trifecta` historical base rows — real historical odds data used by research/backtests
- unique `(race_id,ticket)` odds index — heavily used and enforces identity
- odds primary key — schema semantic preserve
- `idx_v2_odds_race_id` — actively used; planner evidence shows it is useful
- realtime odds indexes — both required/preserve
- full `learning_all` pause — **blocked**, because it changes a Production-scored previous-odds path
- label-scoping `_fetch_previous_odds()` — model-input semantic change, not storage maintenance
- automatic purchase or LINE changes — unrelated to capacity and remain out of scope

## 6. Fresh backup is the common Production gate

The visible backup referenced during research was created 2026-08-23 and is too old to close a 2026-09-12 cleanup recovery gate.

Before **any** Production row deletion, standalone-index removal, physical rewrite, or archive-delete phase, require a fresh restorable recovery point.

Backup creation/restore is itself a Production action and requires explicit user approval. This runbook does not create one.

## 7. One-change-at-a-time execution policy

If explicit Production approval is later granted, do not combine candidates.

Recommended isolation order is:

1. approve/create fresh recovery point;
2. execute exactly one approved candidate;
3. re-check disk, DB health, Production pipelines, and read paths;
4. observe at least one normal operating cycle when relevant;
5. only then consider a second capacity action.

This prevents ambiguous rollback and makes the actual physical-capacity effect measurable.

## 8. What normal `DELETE` and `VACUUM` mean for Railway capacity

- `DELETE` marks tuples removable; it does not itself guarantee filesystem shrink.
- ordinary `VACUUM` generally makes space reusable inside PostgreSQL; it should not be assumed to reduce Railway volume usage proportionally.
- `VACUUM FULL`, table rewrite, or comparable physical rewrite can return more space to the filesystem but requires stronger downtime/locking/free-space planning and a separate explicit approval.
- dropping a standalone index is structurally different: the index relation itself is removed, so it is the cleanest currently studied discrete physical-capacity candidate, though actual Railway metric movement still must be measured rather than assumed.

## 9. Current decision ordering

Given current evidence, if capacity pressure later requires an approved Production action, the research ordering is:

1. **fresh recovery point first**;
2. **race-date standalone index candidate** — best current discrete physical-capacity/risk ratio, but still schema approval only after all gates;
3. **Motor2 conservative retention** — proven semantic invariance, but primarily internal-space reuse unless a separate rewrite is approved;
4. **historical-label cold archive** — largest static logical footprint studied, but archive/restore infrastructure must exist first;
5. **completed-learning cold archive** — meaningful logical footprint but reproducibility/semantic preservation requires stronger archive proof;
6. **odds-only learning** — prevention/operational optimization, not an emergency reclaim measure.

This ordering is **not authorization** to perform any of the above.

## 10. Current gate

`VOLUME_CURRENT_ABOUT_4_183_OF_5_GB / LOGICAL_DB_ABOUT_3700_MB / NO_EXACT_EXHAUSTION_FORECAST / FRESH_BACKUP_REQUIRED_BEFORE_MUTATION / RACE_DATE_INDEX_FIRST_RESEARCH_CANDIDATE_ONLY / MOTOR2_ZERO_DIFF_BUT_DELETE_NOT_AUTHORIZED / HISTORICAL_ARCHIVE_CONTRACT_ONLY / COMPLETED_LEARNING_ARCHIVE_CONTRACT_ONLY / ODDS_ONLY_DEFAULT_OFF / BASE_ODDS_PRESERVE / FULL_LEARNING_PAUSE_BLOCKED / ONE_MUTATION_CLASS_PER_APPROVAL / NO_DELETE / NO_DROP_INDEX / NO_VACUUM / NO_BACKUP_CREATE / NO_RAILWAY_CHANGE / NO_MODEL_CHANGE / NO_LINE_CHANGE / NO_PURCHASE`
