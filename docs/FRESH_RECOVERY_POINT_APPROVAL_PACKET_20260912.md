# Fresh Recovery Point Approval Packet — 2026-09-12

Status: **research / approval planning only**

This document does not enable PITR, create a backup, change a backup schedule, resize a volume, upgrade a Railway plan, restore data, redeploy Postgres, change Railway Variables, or mutate the Production database.

It defines the recovery prerequisite that must be closed before any future Production `DELETE`, `DROP INDEX`, physical rewrite, or archive-delete phase.

## 1. Why the current backup is not sufficient

The current read-only backup inventory resolves the active `postgres-recovery` volume and shows exactly one visible backup:

- name: `Pre-Security-Patch Backup`
- created: 2026-08-23
- expiry: 2026-09-22 at the audited point
- referenced size: about 3582 MB
- used size reported by Railway: 323 MB
- source volume size: 5000 MB

That backup predates the current 2026-09-12 data state by weeks. It is useful historical recovery evidence, but it is too old to be the immediate rollback point for a new capacity mutation.

Therefore all cleanup/schema-removal candidates remain blocked by:

`FRESH_RECOVERY_POINT_REQUIRED`

## 2. Current Production storage context

Read-only Railway metadata/metrics on 2026-09-12 JST:

- service: `postgres-recovery`
- volume state: READY
- volume capacity: 5000 MB
- current volume usage from the backup metadata audit: about `4191.019 MB`
- separate service metric snapshots remain around `4.18 GB / 5 GB`
- PostgreSQL logical database: about `3.88 GB` in the latest integrated audit

The project is on Railway Hobby, whose documented volume size limit is **5 GB**.

## 3. Critical Railway manual-backup constraint

Current Railway documentation states:

- manual volume backups are limited to **50% of the volume's total size**;
- if data exceeds that threshold, Railway recommends growing the volume first or contacting support to raise the limit;
- Hobby volume size limit is **5 GB**.

At roughly 4.19 GB used on a 5 GB volume, a manual backup would need a volume capacity of at least roughly 8.4 GB merely to place current usage at or below 50%.

That exceeds the Hobby 5 GB volume limit.

Therefore the simple plan:

`manual fresh volume backup on the existing 5 GB Hobby volume`

is currently treated as **BLOCKED / NOT RELIABLE**.

Do not attempt `railway postgres pitr backup create` against Production until this limit is resolved and explicit approval is given.

## 4. Current backup schedule state — now confirmed read-only

Integrated storage audit run `34682494855` (run #109) extended the existing Railway GraphQL backup metadata query with `volumeInstanceBackupScheduleList`. The script is statically guarded against GraphQL mutations and backup create/delete/restore operations.

At **2026-09-12 08:10:41 UTC / 17:10:41 JST**, the current Production result was:

```text
STORAGE_RETENTION_BACKUP_VOLUME=resolved:true service_match:true state:READY size_mb:5000 current_size_mb:4191.019007999999
STORAGE_RETENTION_BACKUP_COUNT=1
STORAGE_RETENTION_BACKUP_SCHEDULE_COUNT=0
STORAGE_RETENTION_BACKUP_SCHEDULE=NONE
STORAGE_RETENTION_BACKUP_RESULT=PASS_METADATA_VISIBLE
```

Therefore the current state is no longer unknown:

- Daily volume backup schedule: **not configured**
- Weekly volume backup schedule: **not configured**
- Monthly volume backup schedule: **not configured**
- fresh scheduled backup: **none**
- visible backup count: **1**, still the 2026-08-23 backup

Historical 2026-08-30 recovery facts also reported schedule count zero, so the new 2026-09-12 audit independently reconfirms that no volume-backup schedule is configured now.

No Railway setting was changed by this audit.

## 5. Railway recovery mechanisms currently documented

### A. Manual volume backup

Railway CLI supports an on-demand backup command:

```text
railway postgres pitr backup create --service postgres-recovery --name <name>
```

This is a Production mutation and is **not authorized by this document**.

Current blocker: the documented 50%-of-volume manual-backup limit.

### B. Scheduled volume backup

Railway supports Daily / Weekly / Monthly volume-backup schedules.

Documented retention:

- Daily: every 24 hours, kept 6 days
- Weekly: every 7 days, kept 27 days
- Monthly: every 30 days, kept 89 days

The current Production schedule list is now confirmed empty. The Railway CLI distinguishes volume-backup scheduling from PITR enablement and documents a Daily schedule operation such as:

```text
railway postgres pitr schedule set --daily --service postgres-recovery
```

The documentation's 50% statement specifically identifies **manual backups**. Research has not proven that a newly enabled scheduled backup will successfully create a fresh backup for the current ~4.19/5 GB volume, nor how soon the first snapshot will appear after enabling the schedule.

Therefore setting Daily is not itself a recovery point. If ever explicitly approved, the gate closes only after a new backup actually appears and its metadata is verified.

Changing a schedule is a Railway Production configuration change and requires separate explicit approval.

### C. Point-in-Time Recovery (PITR)

Current Railway Postgres supports PITR through pgBackRest.

When PITR is enabled on a standalone Postgres service, Railway documents that it:

1. creates a `Postgres-PITR` storage bucket;
2. sets `WAL_ARCHIVE_*` Variables on the Postgres service;
3. redeploys the service;
4. starts asynchronous WAL archiving;
5. takes the first pgBackRest base backup once archiving is healthy;
6. then continues weekly full + daily differential backup coverage with roughly four weeks of retained history.

Important recovery property:

- PITR restore creates a **new sibling Postgres service**;
- the source service is not modified by the restore itself.

This is operationally attractive for future rollback verification because a restore does not overwrite the source database.

However, current Railway CLI/docs require an official Railway PostgreSQL image and instruct PITR users to run a **major version tag** such as `postgres-ssl:18` rather than a pinned minor version.

Current Production `postgres-recovery` is instead configured as the official image by exact digest:

```text
ghcr.io/railwayapp-templates/postgres-ssl@sha256:e617e80d34d40def28ab197662197acc5cd6c1dc120db9cf38d835a2386c226c
```

That digest pin was intentional during the 2026-08-31 recovery: read-only verification found that the then-current `postgres-ssl:18` tag had drifted to a different digest while the deleted Production digest remained available. The recovery therefore froze the old digest to reproduce the deleted database runtime as closely as possible.

Consequences:

- the current image is official, but it is **not expressed as the documented major-tag form**;
- PITR compatibility with this digest-pinned source is not proven;
- changing the source from the frozen digest back to `postgres-ssl:18` would select the current tag digest, which historical evidence already showed differs from the recovered digest;
- such an image-source change is itself a material Production deployment change and must not be bundled into backup enablement without explicit review/approval.

Therefore PITR remains a promising recovery mechanism, but its present status is:

`PITR_TECHNICALLY_AVAILABLE / CURRENT_DIGEST_PIN_COMPATIBILITY_NOT_PROVEN / IMAGE_POLICY_CHANGE_MAY_BE_REQUIRED`

PITR is also not retroactive: recovery coverage starts only after the first post-enable base backup.

## 6. Candidate recovery paths

### Path R1 — enable Daily volume backup schedule only

Research assessment: **first Production approval candidate / least image-invasive native path**.

Current baseline is unambiguous: schedule count is zero.

If ever selected, use a deliberately narrow operating window:

1. re-read current schedule list immediately before change;
2. obtain explicit approval for **Daily volume backup schedule only**;
3. do not enable PITR, Weekly, Monthly, resize, change image, or perform cleanup in the same approval;
4. apply Daily schedule only;
5. verify schedule metadata after the setting change;
6. wait for an actual fresh backup to appear;
7. verify its `createdAt`, `expiresAt`, referenced size, volume identity, and current service/volume association;
8. verify normal PostgreSQL/service health;
9. if no fresh backup appears or the operation errors, stop and do not proceed to cleanup;
10. even after a fresh backup appears, request a separate approval for any later DROP/DELETE/VACUUM action.

This packet does **not** authorize step 4.

### Path R2 — PITR enablement and health proof

Research assessment: **strongest long-term recovery design, but currently carries an unresolved image-policy compatibility issue and a larger Production configuration change**.

Required before enablement can even be requested safely:

1. confirm from Railway whether digest-pinned `postgres-ssl` is accepted by PITR as-is;
2. if a major tag is required, separately review the recovered old digest versus the current `:18` digest and migration risk;
3. do not silently change image source as part of a PITR command.

If PITR is later selected and image compatibility is resolved:

1. explicit approval to enable PITR on `postgres-recovery`;
2. record pre-change source image/digest, service config and current volume metrics;
3. enable PITR;
4. confirm redeploy health and normal database availability;
5. wait until PITR status proves archiving healthy and the first base backup/restore window exists;
6. record the earliest restorable timestamp;
7. only then close the recovery gate for a later, separately approved cleanup action.

Do **not** combine image-policy change, PITR enablement, and destructive cleanup in one approval or one operating window.

### Path R3 — raise the manual-backup ceiling, then create an on-demand backup

Possible mechanisms include a larger permitted volume/plan or Railway support raising the applicable limit.

Current Hobby volume max is 5 GB, while current data usage would require at least about 8.4 GB for the documented 50% manual-backup rule.

This path can therefore require a plan/limit change. Any plan upgrade, paid-resource change, volume resize, or support interaction requires explicit approval.

Railway volume resize expands capacity and is not a clean temporary grow-and-shrink mechanism, so this is not preferred as the first recovery action.

## 7. Recovery-point acceptance criteria

A recovery gate is not closed merely because a setting or command returned success.

For any selected recovery method, capture at minimum:

- target project/environment/service identity;
- recovery mechanism type;
- creation/coverage timestamp after the current data state;
- source volume identity and capacity;
- source image/tag/digest before and after any approved configuration change;
- backup/PITR health status;
- current referenced/base-backup evidence where exposed;
- expiry/retention horizon sufficient to cover the planned cleanup and observation period;
- exact restoration procedure documented before cleanup;
- no unexpected staged Railway changes;
- normal Postgres health after creation/enablement.

For PITR specifically, require a non-empty current restore range and healthy archiver/base-backup state.

For a volume backup specifically, require the backup to appear in the backup inventory with a fresh timestamp and plausible source-size reference.

## 8. Restore testing boundary

### Volume backup restore

Railway documents volume-backup restore as a staged change that mounts a restored volume at the original mount path and retains the previous volume unmounted. Completing the restore redeploys the service on restored data.

The CLI also describes standalone volume backup restore as an **in-place restore**.

Therefore a Production volume-backup restore test is itself destructive/high-impact and is **not** part of the routine fresh-backup gate.

### PITR restore

PITR restore creates a sibling Postgres service and leaves the source untouched. This is the safer mechanism if a future explicit approval asks for empirical restore proof.

Even a sibling restore creates new Railway resources and storage, so it still requires explicit approval and should be performed separately from cleanup.

## 9. Cost boundary

Railway documents PITR as using normal storage-bucket storage and service network-egress meters; there is no separate PITR fee, but it is not cost-free.

Volume backups are incremental/copy-on-write and billed for incremental stored data.

No paid-plan change, support request, bucket creation, PITR enablement, volume enlargement, or new recurring backup configuration is authorized here.

## 10. Recommended ordering

Before asking for a destructive capacity action, resolve recovery capability first.

Current ordering:

1. **do not attempt a manual backup under the current 5 GB / ~4.19 GB state**;
2. current schedule is already confirmed zero by read-only run #109;
3. if the user explicitly approves a recovery setting change, make **Daily volume backup schedule only** the first candidate;
4. after enabling Daily, wait for and verify an actual fresh backup; do not combine cleanup with schedule enablement;
5. evaluate PITR separately only after digest-pin compatibility is resolved;
6. use plan/limit enlargement only if necessary and explicitly approved;
7. after a fresh recovery point is proven, return to a separate approval request for exactly one capacity mutation candidate.

## 11. No implicit authorization

This packet does not authorize:

- `railway postgres pitr enable`
- `railway postgres pitr backup create`
- `railway postgres pitr schedule set`
- any Postgres image/tag/digest change
- any backup lock/delete/restore
- any volume resize
- any Railway plan upgrade
- any support request
- any sibling restore service creation
- any `DELETE`, `DROP INDEX`, `VACUUM`, `VACUUM FULL`, or table rewrite

## 12. Current gate

`OLD_BACKUP_TOO_STALE_FOR_NEW_CLEANUP / CURRENT_BACKUP_COUNT_1 / CURRENT_SCHEDULE_COUNT_0 / DAILY_WEEKLY_MONTHLY_ALL_UNCONFIGURED / HOBBY_VOLUME_MAX_5GB / CURRENT_VOLUME_ABOUT_4_19GB / MANUAL_BACKUP_50PCT_LIMIT_CONFLICT / MANUAL_FRESH_BACKUP_BLOCKED_ON_CURRENT_HOBBY_CAPACITY / DAILY_SCHEDULE_FIRST_APPROVAL_CANDIDATE_ONLY / DAILY_SCHEDULE_SUCCESS_NOT_YET_PROVEN / PITR_AVAILABLE_BUT_PRODUCTION_CONFIG_CHANGE / CURRENT_POSTGRES_DIGEST_PINNED / RECOVERY_TAG_DRIFT_PREVIOUSLY_CONFIRMED / PITR_MAJOR_TAG_REQUIREMENT_CONFLICT_NOT_RESOLVED / PITR_IMAGE_POLICY_CHANGE_MAY_BE_REQUIRED / FRESH_RECOVERY_POINT_NOT_YET_CLOSED / NO_BACKUP_CREATE / NO_PITR_ENABLE / NO_SCHEDULE_CHANGE / NO_IMAGE_CHANGE / NO_VOLUME_RESIZE / NO_PLAN_CHANGE / NO_RESTORE / NO_DELETE / NO_DROP_INDEX / NO_VACUUM`
