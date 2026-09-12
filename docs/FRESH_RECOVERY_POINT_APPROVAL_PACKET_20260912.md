# Fresh Recovery Point Approval Packet — 2026-09-12

Status: **research / approval planning only**

This document does not enable PITR, create a backup, change a backup schedule, resize a volume, upgrade a Railway plan, restore data, redeploy Postgres, change Railway Variables, or mutate the Production database.

It defines the recovery prerequisite that must be closed before any future Production `DELETE`, `DROP INDEX`, physical rewrite, or archive-delete phase.

## 1. Why the current backup is not sufficient

The read-only backup inventory used by the storage research found the visible named backup:

- name: `Pre-Security-Patch Backup`
- created: 2026-08-23
- expiry: 2026-09-22 at the audited point
- referenced size: about 3582 MB

That backup predates the current 2026-09-12 data state by weeks. It is useful historical recovery evidence, but it is too old to be the immediate rollback point for a new capacity mutation.

Therefore all cleanup/schema-removal candidates remain blocked by:

`FRESH_RECOVERY_POINT_REQUIRED`

## 2. Current Production storage context

Read-only Railway metrics on 2026-09-12 JST:

- service: `postgres-recovery`
- volume capacity: 5 GB
- current disk usage: about 4.183 GB
- nominal headroom: about 0.817 GB
- PostgreSQL logical database: about 3700 MB

The project is on Railway Hobby, whose documented volume size limit is **5 GB**.

## 3. Critical Railway manual-backup constraint

Current Railway documentation states:

- manual volume backups are limited to **50% of the volume's total size**;
- if data exceeds that threshold, Railway recommends growing the volume first or contacting support to raise the limit;
- Hobby volume size limit is **5 GB**.

At about 4.183 GB used on a 5 GB volume, a manual backup would need a volume capacity of at least roughly **8.366 GB** merely to place current usage at or below 50%.

That exceeds the Hobby 5 GB volume limit.

Therefore the simple plan:

`manual fresh volume backup on the existing 5 GB Hobby volume`

is currently treated as **BLOCKED / NOT RELIABLE**.

Do not attempt `railway postgres pitr backup create` against Production until this limit is resolved and explicit approval is given.

## 4. Railway recovery mechanisms currently documented

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

The documentation's 50% statement specifically identifies **manual backups**. This research has not proven that a newly enabled scheduled backup will successfully create a fresh backup for the current ~4.18/5 GB volume, nor has it measured how soon the first scheduled snapshot would occur.

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

But enabling PITR is not a read-only action. It changes Variables, creates a bucket, redeploys Postgres, and adds ongoing storage/network usage. It therefore requires explicit Production approval.

PITR is also not retroactive: recovery coverage starts only after the first post-enable base backup.

## 5. Candidate recovery paths

### Path R1 — PITR enablement and health proof

Research assessment: **strongest recovery design, but a larger Production configuration change**.

Required approvals/actions if ever selected:

1. explicit approval to enable PITR on `postgres-recovery`;
2. confirm the service image remains an official Railway Postgres image on a supported major tag;
3. record pre-change service config and current volume metrics;
4. enable PITR;
5. confirm redeploy health and normal database availability;
6. wait until PITR status proves archiving healthy and the first base backup/restore window exists;
7. record the earliest restorable timestamp;
8. only then close the recovery gate for a later, separately approved cleanup action.

Do **not** combine PITR enablement and a destructive cleanup in one approval or one operating window.

### Path R2 — scheduled volume backup

Research assessment: **smaller conceptual change than PITR, but current success/timing at >50% volume usage is not yet proven**.

Required if ever selected:

1. explicit approval to change the backup schedule;
2. choose a retention cadence;
3. verify a new backup actually appears after the setting change;
4. confirm its `createdAt`, `expiresAt`, referenced size, volume identity, and current service/volume association;
5. do not treat the setting itself as a completed recovery point until the backup exists.

### Path R3 — raise the manual-backup ceiling, then create an on-demand backup

Possible mechanisms include a larger permitted volume/plan or Railway support raising the applicable limit.

Current Hobby volume max is 5 GB, while current data usage would require at least about 8.366 GB for the documented 50% manual-backup rule.

This path can therefore require a plan/limit change. Any plan upgrade, paid-resource change, volume resize, or support interaction requires explicit approval.

A volume resize is capacity/configuration work and must not be performed silently as part of cleanup.

## 6. Recovery-point acceptance criteria

A recovery gate is not closed merely because a command returned success.

For any selected recovery method, capture at minimum:

- target project/environment/service identity;
- recovery mechanism type;
- creation/coverage timestamp after the current data state;
- source volume identity and capacity;
- backup/PITR health status;
- current referenced/base-backup evidence where exposed;
- expiry/retention horizon sufficient to cover the planned cleanup and observation period;
- exact restoration procedure documented before the cleanup;
- no unexpected staged Railway changes;
- normal Postgres health after creation/enablement.

For PITR specifically, require a non-empty current restore range and healthy archiver/base-backup state.

For a volume backup specifically, require the backup to appear in the backup inventory with a fresh timestamp and plausible source-size reference.

## 7. Restore testing boundary

### Volume backup restore

Railway documents volume-backup restore as a staged change that mounts a restored volume at the original mount path and retains the previous volume unmounted. Completing the restore redeploys the service on restored data.

The CLI also describes standalone volume backup restore as an **in-place restore**.

Therefore a Production volume-backup restore test is itself destructive/high-impact and is **not** part of the routine fresh-backup gate.

### PITR restore

PITR restore creates a sibling Postgres service and leaves the source untouched. This is the safer mechanism if a future explicit approval asks for empirical restore proof.

Even a sibling restore creates new Railway resources and storage, so it still requires explicit approval and should be performed separately from cleanup.

## 8. Cost boundary

Railway documents PITR as using normal storage-bucket storage and service network-egress meters; there is no separate PITR fee, but it is not cost-free.

Volume backups are incremental/copy-on-write and billed for incremental stored data.

No paid-plan change, support request, bucket creation, PITR enablement, volume enlargement, or new recurring backup configuration is authorized here.

## 9. Recommended research ordering

Before asking for a destructive capacity action, resolve recovery capability first.

Current research ordering:

1. **do not attempt a manual backup under the current 5 GB / ~4.18 GB state**;
2. evaluate PITR versus scheduled backup as the two non-destructive-to-data recovery mechanisms available without deleting anything;
3. if PITR is selected, request explicit approval for PITR enablement as its own Production change;
4. if scheduled backup is selected, request explicit approval for the schedule change and require observed successful backup creation before proceeding;
5. use plan/limit enlargement only if necessary and explicitly approved;
6. after a fresh recovery point is proven, return to a separate approval request for exactly one capacity mutation candidate.

## 10. No implicit authorization

This packet does not authorize:

- `railway postgres pitr enable`
- `railway postgres pitr backup create`
- `railway postgres pitr schedule set`
- any backup lock/delete/restore
- any volume resize
- any Railway plan upgrade
- any support request
- any sibling restore service creation
- any `DELETE`, `DROP INDEX`, `VACUUM`, `VACUUM FULL`, or table rewrite

## 11. Current gate

`OLD_BACKUP_TOO_STALE_FOR_NEW_CLEANUP / HOBBY_VOLUME_MAX_5GB / CURRENT_VOLUME_ABOUT_4_183GB / MANUAL_BACKUP_50PCT_LIMIT_CONFLICT / MANUAL_FRESH_BACKUP_BLOCKED_ON_CURRENT_HOBBY_CAPACITY / PITR_AVAILABLE_BUT_PRODUCTION_CONFIG_CHANGE / PITR_RESTORE_SOURCE_UNTOUCHED / SCHEDULED_BACKUP_AVAILABLE_BUT_NOT_PROVEN_AT_CURRENT_USAGE / PLAN_OR_LIMIT_CHANGE_REQUIRES_APPROVAL / FRESH_RECOVERY_POINT_NOT_YET_CLOSED / NO_BACKUP_CREATE / NO_PITR_ENABLE / NO_SCHEDULE_CHANGE / NO_VOLUME_RESIZE / NO_PLAN_CHANGE / NO_RESTORE / NO_DELETE / NO_DROP_INDEX / NO_VACUUM`
