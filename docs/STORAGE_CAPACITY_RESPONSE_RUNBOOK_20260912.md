# Storage Capacity Response Runbook — 2026-09-12

Status: **research / approval planning only**

This document does not authorize any Production mutation. In particular it does not authorize `DELETE`, `DROP INDEX`, `VACUUM`, `VACUUM FULL`, `ANALYZE`, backup creation/restore, Railway Production configuration changes, Cron/service changes, model/threshold changes, LINE changes, Forward persistence changes, or purchase behavior.

## 1. Current capacity snapshot

Latest read-only evidence on 2026-09-12 JST:

- active DB service: `postgres-recovery`
- volume state: READY
- volume capacity: **5000 MB**
- volume current size from Railway backup metadata audit: **4191.019 MB**
- service disk metric remains around **4.18 GB / 5 GB**
- PostgreSQL logical database from integrated audit: **3,880,515,263 bytes**
- largest relation: `v2_odds_trifecta`, **1,898,651,648 bytes**
- CPU remains generally low; recent memory remains below the 8 GB service limit.

Railway physical volume usage and PostgreSQL logical relation size are different measurements. WAL, temporary files, filesystem overhead, relation/index allocation and transient activity prevent treating their difference as directly reclaimable space.

No exact exhaustion date is asserted. Capacity is a **weeks-scale operational issue**, not an immediate outage, and secondary-sport datasets must not be co-located here.

## 2. Current growth attribution

The seven-completed-day logical-growth audit measured about **15.31 MB/day** across ten tracked tables. Largest tracked contributors were:

1. `v2_v24_motor2_forward_shadow`: about **6.06 MB/day** logical payload
2. `v2_realtime_odds_snapshots`: about **5.03 MB/day**
3. `v2_odds_trifecta`: about **1.72 MB/day**
4. Racer Course stats: about **0.61 MB/day**
5. realtime condition tables / Opponent Pressure: smaller contributors.

This sum is useful for attribution only; it is not a physical Railway-volume forecast.

## 3. Mandatory ordering rule

For any future Production capacity action:

1. re-measure current disk and logical DB sizes;
2. confirm the exact candidate and dependencies;
3. **close the fresh recovery-point gate first**;
4. perform only one explicitly approved mutation class;
5. verify DB/application health and physical/logical capacity afterward;
6. observe a normal operating cycle when relevant;
7. only then consider another action.

Never bundle `DELETE + VACUUM + DROP INDEX + archive cleanup` into one approval.

## 4. Recovery gate — now fully characterized

The visible backup remains:

- `Pre-Security-Patch Backup`
- created 2026-08-23
- referenced size about 3582 MB
- too old to serve as the immediate rollback point for a new capacity mutation.

Current Railway documentation states that **manual volume backups are limited to 50% of total volume capacity**. At about 4.19 GB used on a Hobby 5 GB volume, the existing volume cannot satisfy that rule; Hobby's documented volume ceiling is also 5 GB.

Integrated read-only run `34682494855` (#109), at 2026-09-12 17:10 JST, independently queried `volumeInstanceBackupScheduleList` and confirmed:

- backup count: **1**
- schedule count: **0**
- Daily: not configured
- Weekly: not configured
- Monthly: not configured.

Therefore the recovery paths rank:

1. **Daily volume-backup schedule only** — first Production approval candidate because it is the least image-invasive native path. Setting Daily is not itself a recovery point; a fresh backup must actually appear and be verified.
2. **PITR** — stronger long-term model, but current `postgres-recovery` uses an intentional exact image digest while Railway PITR guidance expects official major-tag operation. Digest/tag compatibility must be resolved first.
3. **Plan/limit enlargement + manual backup** — larger paid/configuration change and not a clean temporary maneuver because Railway volume resize is expansion-only.

No recovery setting has been changed.

Reference: PR #344 / `docs/FRESH_RECOVERY_POINT_APPROVAL_PACKET_20260912.md`.

## 5. Candidate priority matrix

### Priority A — `idx_v2_odds_race_date` standalone index

Current evidence:

- size: **70,942,720 bytes** (~67.7 MiB)
- no constraint ownership
- exact recreate DDL frozen in PR #341
- pure static repository audit checks **72** odds SQL strings and finds **0 direct `v2_odds_trifecta.race_date` consumers**
- static tests: **8/8 PASS**
- earliest dedicated index audit observed `idx_scan=0`
- later cumulative counter rose to 9, but that counter is **known research/audit contaminated**:
  - early dedicated index diagnostics executed direct race-date sample queries before commit `ef626c91920ef189f704ad2be59ff27d1e4c8a9d` removed the self-contaminating lookup;
  - early current-growth run `34674650540` also executed one direct bounded odds-table race-date query before commit `5a74fb58cb76180e241c4e43ce67ba8cdb4bea51` switched date resolution through `v2_races`;
  - current integrated audit uses static `EXPLAIN` literals and does not intentionally data-sample the candidate index.

Therefore the current `idx_scan=9` is **not valid evidence of nine organic Production uses**. It also cannot be perfectly decomposed after the fact from the cumulative counter, so no claim is made that every increment is explained.

Why it remains the first physical-capacity research candidate after recovery is solved:

- a standalone index is a discrete physical relation, unlike row deletion that primarily creates reusable heap space;
- checked-in direct consumers are currently zero;
- exact recreation metadata is known.

Mandatory gates before any request to remove it:

- fresh recovery point;
- fresh index identity/constraint/valid-ready-live check;
- current pure static dependency audit;
- non-self-contaminating workload evidence / clean observation baseline;
- explicit Production schema-change approval;
- one-index-only execution plan, with PostgreSQL concurrent-operation constraints reviewed;
- post-change health/query/capacity verification.

Current state: **`NO_DROP_AUTHORIZED`**.

Reference: PR #341 / `docs/ODDS_RACE_DATE_INDEX_APPROVAL_PACKET_20260912.md`.

### Priority B — Motor2 conservative retention

Current evidence:

- Motor2 relation: about **205.8 MB**
- protected-output invariance remains zero-diff for Performance, Robustness PRE/FINAL and current PRE health
- conservative final/final candidate: **42,552 rows**
- candidate/protected intersection: zero
- recent-seven-day conservative candidate estimate: **14,578 rows / 13,759,792 logical bytes**
- recent candidate growth about **1.97 MB/day logical payload**.

Why it ranks below the standalone index:

- `DELETE` makes PostgreSQL heap space reusable but does not promise equivalent Railway-volume shrink;
- physical rewrite/VACUUM FULL would be a separate higher-impact action;
- candidate digest must be refreshed immediately before any future execution.

Mandatory gates: fresh recovery point, exact current digest, zero-diff invariance, explicit bounded `DELETE` approval, and separate approval for any later VACUUM/rewrite.

Current state: **`NO_DELETE_AUTHORIZED / NO_VACUUM_AUTHORIZED`**.

### Priority C — completed `historical` realtime labels to cold archive

Research inventory:

- total historical rows: **880,974**
- logical payload: about **466.5 MB**
- audited historical series ends 2026-08-30, so this is a large static footprint rather than the current daily-growth source.

No confirmed steady-state Production read dependency currently requires these rows to remain hot, but research/replay/repair dependencies exist. Railway Storage Bucket is a plausible low-cost archive target, but a single bucket is not accepted as the sole immutable recovery copy because bucket object versioning/object lock/automatic backup are not currently provided.

Required before any future cleanup: real archive destination, explicit-column lossless export, manifest/count/schema/content digests, read-back verification, isolated restore proof, runtime dependency recheck, fresh DB recovery point, exact bounded deletion inventory, and separate explicit deletion approval.

Current state: **`PRESERVE HOT / NO_DELETE_AUTHORIZED`**.

### Priority D — completed `learning_all` rows to cold archive

Latest integrated evidence continues to show a large completed-learning footprint and near-total identity overlap with completed `final_ab`. However:

- live `learning_all` cannot simply be stopped because FINAL previous-odds logic can cross labels;
- completed rows retain reproducibility/research value;
- pure archive manifest/restore contract exists, but no real archive destination/restore proof exists.

Current state: **`PRESERVE / NO_DELETE_AUTHORIZED`**.

### Priority E — odds-only `learning_all` mode

PR #337 defines a default-off research mode that would preserve learning odds cadence while skipping duplicated learning-side non-odds collection.

Its capacity benefit is small compared with the candidates above; its stronger benefit is reduced duplicate HTTP/parsing/write load. Activation changes Production runtime collection behavior and remains approval-gated.

Current state: **`DEFAULT_OFF / NO_DEPLOY / NO_RAILWAY_CHANGE`**.

## 6. Explicit preserve / blocked actions

Do not treat these as capacity cleanup candidates under current evidence:

- `v2_odds_trifecta` historical rows — real historical odds data
- unique `(race_id,ticket)` odds index — heavily used and identity-enforcing
- odds primary key — schema semantic preserve
- `idx_v2_odds_race_id` — actively used and planner-selected
- realtime odds indexes — both required/preserve
- full `learning_all` pause — blocked because of cross-label previous-odds coupling
- label-scoping `_fetch_previous_odds()` — model-input semantic change, not maintenance
- LINE or purchase changes — unrelated to capacity.

## 7. One-change-at-a-time execution policy

If explicit Production approval is later granted:

1. approve/prove one recovery mechanism;
2. execute exactly one approved capacity candidate;
3. re-check disk, DB health, Production pipelines and read paths;
4. observe at least one normal operating cycle when relevant;
5. only then consider a second action.

This keeps rollback attribution clear and allows physical-capacity effects to be measured rather than assumed.

## 8. DELETE / VACUUM / index semantics

- `DELETE` marks tuples removable; it does not itself guarantee filesystem shrink.
- ordinary `VACUUM` makes space reusable inside PostgreSQL and should not be assumed to reduce Railway volume usage proportionally.
- `VACUUM FULL` / table rewrite can return more space to the filesystem but needs separate locking/downtime/free-space review and approval.
- dropping a standalone index removes a separate index relation, making it the cleanest currently studied discrete physical-capacity lever, but exact Railway metric movement is still an observation, not a guarantee.

For any future approved race-date index removal, PostgreSQL 18 concurrent-operation restrictions must be respected; no DROP/CREATE/REINDEX is authorized by this document.

## 9. Current research ordering

1. **Daily backup schedule only, if explicitly approved, then prove a fresh backup exists**
2. **race-date standalone index candidate**, only after recovery + all schema gates
3. **Motor2 conservative retention**
4. **historical-label cold archive**, after real archive/restore proof
5. **completed-learning cold archive**, after real archive/restore proof
6. **odds-only learning**, prevention/operational optimization rather than emergency reclaim.

This ordering is **not authorization**.

## 10. Current gate

`VOLUME_CURRENT_ABOUT_4191_OF_5000_MB / LOGICAL_DB_ABOUT_3881_MB / NO_EXACT_EXHAUSTION_FORECAST / CURRENT_BACKUP_COUNT_1 / CURRENT_BACKUP_SCHEDULE_COUNT_0 / DAILY_WEEKLY_MONTHLY_UNCONFIGURED / FRESH_RECOVERY_POINT_REQUIRED / MANUAL_BACKUP_50PCT_LIMIT_CONFLICT / HOBBY_MAX_5GB / DAILY_SCHEDULE_FIRST_APPROVAL_CANDIDATE_ONLY / DAILY_SCHEDULE_NOT_AUTHORIZED / RACE_DATE_INDEX_INITIAL_SCAN_ZERO / RACE_DATE_COUNTER_RESEARCH_CONTAMINATED / STATIC_DIRECT_RACE_DATE_CONSUMERS_ZERO / RACE_DATE_INDEX_FIRST_SCHEMA_RESEARCH_CANDIDATE_ONLY / MOTOR2_ZERO_DIFF_BUT_DELETE_NOT_AUTHORIZED / HISTORICAL_ARCHIVE_CONTRACT_ONLY / COMPLETED_LEARNING_ARCHIVE_CONTRACT_ONLY / ODDS_ONLY_DEFAULT_OFF / BASE_ODDS_PRESERVE / FULL_LEARNING_PAUSE_BLOCKED / ONE_MUTATION_CLASS_PER_APPROVAL / NO_DELETE / NO_DROP_INDEX / NO_VACUUM / NO_BACKUP_CREATE / NO_PITR_ENABLE / NO_SCHEDULE_CHANGE / NO_VOLUME_RESIZE / NO_PLAN_CHANGE / NO_RAILWAY_CHANGE / NO_MODEL_CHANGE / NO_LINE_CHANGE / NO_PURCHASE`
