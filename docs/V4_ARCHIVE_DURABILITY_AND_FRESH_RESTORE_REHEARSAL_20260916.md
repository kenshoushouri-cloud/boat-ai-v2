# V4 archive durability / fresh restore rehearsal — 2026-09-16

Status: `RESEARCH_ONLY / NO_BUCKET_CREATED / NO_UPLOAD / NO_DB_MUTATION / NO_RAILWAY_MUTATION`

This document refines the storage-migration gate using current Railway documentation and the already-proven ephemeral archive/read-through evidence. It does not create a Bucket, service, volume, backup, credential, or database. It does not authorize DELETE, VACUUM, schema changes, plan changes, or Production migration.

## 1. Current Railway facts rechecked 2026-09-16

Official Railway documentation currently states:

- Storage Buckets are private S3-compatible object storage.
- Storage price is USD `0.015 / GB-month`.
- S3 API operations are free/unlimited and bucket egress is free.
- Uploads from a Railway service to a Bucket still count as Railway **service egress** because Buckets use the public network.
- Hobby Bucket capacity limit is `1 TB`.
- Buckets are encrypted at rest.
- Bucket instances are environment-scoped.
- Bucket features currently **do not include** server-side encryption configuration, object versioning, object locks, or bucket lifecycle configuration.
- Railway currently provides **no automatic Bucket backups or snapshots**.
- A deleted Bucket is restorable for about 52 hours, after which deletion is permanent.
- Hobby Volume size is `5 GB`; Pro default Volume size is `50 GB` and can be increased.
- Railway Volumes currently **cannot be downsized**; only expansion is supported.
- Railway documents approximately `2-3%` filesystem metadata usage for Volumes.

Authoritative references checked for this contract:

- `https://docs.railway.com/storage-buckets`
- `https://docs.railway.com/storage-buckets/billing`
- `https://docs.railway.com/volumes`
- `https://docs.railway.com/volumes/reference`

## 2. Archive target decision

Railway Storage Bucket remains the preferred **primary object archive candidate** because it is S3-compatible, cheap at the current expected scale, environment-scoped, and directly compatible with the existing archive abstraction.

However, a Railway Bucket is **not accepted as the sole post-deletion recovery copy** under this project because the platform currently lacks object versioning, object lock, lifecycle protection, and automatic Bucket backups.

Therefore old Production rows remain non-deletion-eligible until the archive partition has both:

1. a verified primary immutable-by-contract object copy; and
2. an independently recoverable second protection layer.

The second layer may be satisfied by one of the following after separate review:

- a fresh restorable PostgreSQL recovery point that still contains the source partition through the destructive-change rollback window;
- an independently stored second archive copy with its own readback/hash proof;
- another recovery mechanism that is independently recoverable and explicitly approved.

A single Bucket object plus a local manifest is insufficient.

## 3. Immutable-by-contract object policy

Because Bucket object lock/versioning are unavailable, immutability must be enforced by the archive protocol:

- content-addressed or deterministic partition keys;
- never overwrite an existing key with different bytes;
- compare existing manifest/object hashes before any retry;
- `same hashes => idempotent success`;
- `different hashes => FAIL_CONFLICT`;
- data object first, permanent-target readback second, manifest write last;
- manifest records canonical payload SHA-256 and compressed-object SHA-256;
- credentials used by an exporter must not have unrelated Production DB mutation authority.

This is application-level immutability, not a claim that Railway currently provides WORM/object-lock semantics.

## 4. Fresh logical restore is the Hobby capacity proof

Current Production filesystem/disk usage around 4.4 GB cannot prove that the system safely fits a fresh Hobby 5 GB Volume. The current 20 GB Volume cannot be downsized in place.

The migration capacity gate is therefore based on a **fresh logical retained-set restore**, not current filesystem usage and not DELETE estimates.

Required rehearsal target:

`isolated fresh PostgreSQL instance + exactly the candidate online-retained dataset + production-equivalent schema/indexes`

The rehearsal must not restore archived cold payload into PostgreSQL merely to make the target bigger; cold data belongs in the archive layer if all consumer/recovery gates have passed.

## 5. Rehearsal input contract

Before a rehearsal can be considered decision-grade, freeze:

- source main SHA;
- exact Production schema identity;
- candidate online retention policy per table/label;
- exact retained/cold partition boundaries;
- current-day and Forward evidence exclusions from cold scope;
- retained row counts and digests where practical;
- archive object/manifest hashes for partitions excluded from the fresh PostgreSQL target;
- all required indexes/constraints/extensions;
- migration script SHA.

`ONLINE_RETENTION_DAYS` remains undecided. A 30-day set may be measured as a scenario, but cannot silently become the accepted cutoff.

## 6. Safe rehearsal execution shape

Preferred first rehearsal is **non-Production and ephemeral**:

1. connect to Production PostgreSQL with `default_transaction_read_only=on`;
2. create a fresh isolated PostgreSQL target outside Production;
3. recreate schema, constraints, indexes, sequences, and required extensions;
4. copy the candidate retained rows table-by-table using bounded deterministic ordering;
5. never run source `INSERT/UPDATE/DELETE/DDL/VACUUM`;
6. restore archive-backed research capability separately through the archive reader, not by silently merging cold rows back into the hot DB;
7. run application/readiness checks against the fresh target where safe;
8. measure target PostgreSQL logical/relation sizes after restore/index creation;
9. record target filesystem/volume consumption if the rehearsal environment exposes it;
10. destroy only the ephemeral rehearsal target after evidence is preserved.

Do not use a new Railway Production service/Volume for the first rehearsal without explicit approval. A GitHub Actions PostgreSQL service container or another isolated non-Production target is preferred if it can hold the full retained set within runtime/disk limits.

## 7. Required measurements

At minimum record after the fresh retained-set restore:

- `pg_database_size()`;
- per-table `pg_total_relation_size()`;
- total heap vs index bytes;
- row counts by retained table/label;
- restore duration;
- peak local disk usage if observable;
- largest temporary file / sort spill if observable;
- schema/index completeness check;
- application read-only smoke/readiness result;
- archive-backed historical consumer smoke result;
- source/target retained-row equivalence digest for bounded representative partitions.

Do not infer physical Hobby headroom from logical tuple payload bytes alone.

## 8. Hobby acceptance headroom

A target that merely reports `<5 GB` is not sufficient. Railway documents filesystem metadata overhead, and PostgreSQL also needs operating headroom for growth, maintenance, WAL/temp activity, and failure recovery.

Therefore the decision must explicitly freeze a required headroom policy **before** declaring Hobby fit.

Until that policy is frozen and measured:

`HOBBY_5GB_FIT = NOT_PROVEN`

The proof condition remains:

`FRESH_RESTORE_OBSERVED_SIZE + FROZEN_REQUIRED_HEADROOM <= HOBBY_5GB_LIMIT`

## 9. Cost implication

Bucket storage price is unlikely to be the main October cost blocker at the currently observed data scale, but the exact archive bill must use **actual permanent compressed bytes**, not PostgreSQL relation bytes or logical tuple payload estimates.

Service-to-Bucket uploads can incur Railway service egress. A future permanent exporter should therefore report actual uploaded bytes and expected service egress before activation.

No paid resource should be created solely to validate an estimate that can first be tested in ephemeral CI.

## 10. Current gate

Current state after this contract:

`RAILWAY_BUCKET_PREFERRED_PRIMARY_CANDIDATE / SINGLE_BUCKET_NOT_SUFFICIENT_AS_SOLE_RECOVERY_COPY / SECOND_PROTECTION_LAYER_REQUIRED / CURRENT_20GB_VOLUME_NOT_DOWNSIZABLE / HOBBY_5GB_FRESH_RESTORE_PROOF_REQUIRED / ONLINE_RETENTION_UNDECIDED / NO_BUCKET_CREATED / NO_UPLOAD / NO_DELETE / NO_PRODUCTION_MIGRATION`
