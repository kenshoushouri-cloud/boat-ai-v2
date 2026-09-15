# V4 archive target / retention contract — 2026-09-15

Status: `RESEARCH_ONLY / NO_BUCKET_CREATED / NO_PRODUCTION_RETENTION_CHANGE / NO_DELETE`

This document freezes the next storage-migration contract after the July real-data archive/read-through pilots succeeded. It does not create external storage, upload Production-derived data, change Railway, or authorize deletion of any online row.

## 1. Goal

Move old timing-safe raw/history evidence out of the live PostgreSQL working set **without losing prediction quality, auditability, reproducibility, retraining capability, or restoreability**.

The intended end state is:

- Railway PostgreSQL / Volume: current operational data, recent evidence needed by active consumers, current V4 / Stage2 Forward evidence, results/settlement, and any history whose consumer is not yet archive-capable.
- Immutable object archive: older month-partitioned raw evidence that has passed export/readback/hash/consumer-equivalence/restore gates.
- Research consumers: strict read-through; online first only when the requested partition is fully online, otherwise a verified archive partition. No silent partial merge in V1.

## 2. Preferred permanent archive target

### Preferred: Railway Storage Bucket

Reasoning:

- S3-compatible object storage, so archive code is provider-neutral at the S3 boundary.
- Appropriate for immutable compressed JSONL + manifest objects rather than a live PostgreSQL data directory.
- Railway documentation checked 2026-09-15 lists bucket storage at USD 0.015/GB-month, with S3 API operations and bucket egress free.
- Hobby documentation lists a combined bucket capacity limit of 1 TB, far above the current Boat archive requirement.
- Bucket instances are environment-scoped, reducing accidental cross-environment access.

Important cost note: uploads originating from a Railway service count as **service egress** because buckets use the public network. Therefore the first archive writer should preferably run from a bounded CI/export job or another explicitly reviewed path rather than turning an always-on Production service into a bulk uploader by default.

Official references:

- https://docs.railway.com/storage-buckets
- https://docs.railway.com/storage-buckets/billing
- https://docs.railway.com/guides/storage-buckets-guide

### Secondary/offsite copy: Google Drive

Google Drive may be useful later as a human-accessible secondary/offsite copy of already-frozen archive objects, but it is **not** the preferred primary read-through backend:

- it is not the live PostgreSQL filesystem;
- it does not match the current S3-oriented archive abstraction as naturally;
- automated credential/permission/restore behavior would require a separate contract and connector review.

Do not bulk-upload Production evidence to Drive under this contract.

### Rejected as primary archive

- GitHub Actions artifacts: temporary CI evidence, not a durable database archive contract.
- Git repository / Git LFS: wrong lifecycle and access pattern for large raw data history.
- Current PostgreSQL Volume: that would not reduce the live-volume migration burden.

## 3. Object layout

V1 objects MUST be immutable month partitions. Never overwrite an existing object with different bytes.

Recommended prefix:

```text
boat-ai-v2/archive-contract-v1/
  <table>/
    label=<label-or-none>/
      year=YYYY/
        month=MM/
          YYYY-MM-01_YYYY-MM-last.jsonl.gz
          YYYY-MM-01_YYYY-MM-last.manifest.json
```

Examples:

```text
boat-ai-v2/archive-contract-v1/v2_odds_trifecta/label=none/year=2026/month=07/2026-07-01_2026-07-31.jsonl.gz
boat-ai-v2/archive-contract-v1/v2_odds_trifecta/label=none/year=2026/month=07/2026-07-01_2026-07-31.manifest.json
boat-ai-v2/archive-contract-v1/v2_realtime_odds_snapshots/label=final_ab/year=2026/month=07/2026-07-01_2026-07-31.jsonl.gz
```

Object key must be derivable only from table / label / exact date bounds. A retry with the same logical partition must first compare existing manifest + hashes and fail closed if bytes differ.

## 4. Required manifest fields

The permanent manifest MUST contain at least:

- `archive_contract_version`
- `source_mode=postgresql_read_only`
- `table`
- `label`
- `start_date`
- `end_date`
- ordered PostgreSQL `schema` (`column_name`, `data_type`, `udt_name`)
- deterministic ordered columns
- logical key fields
- row count
- distinct race count where applicable
- min/max race/date provenance
- canonical uncompressed payload byte count
- canonical payload SHA-256
- compressed object byte count
- compressed object SHA-256
- logical-key duplicate count
- `readback_verified=true`
- export code git SHA
- generated UTC timestamp
- `source_rows_deleted=false` at export time
- evidence class (`historical_raw`, `forward_evidence`, etc.)

No manifest with missing schema or ambiguous key is eligible for online deletion.

## 5. Permanent-write protocol

A partition is `ARCHIVE_WRITTEN` only if all steps pass:

1. Source DB connection is `default_transaction_read_only=on`.
2. Export exact bounded month partition using an allow-listed table/label contract.
3. Produce deterministic canonical JSONL then deterministic gzip.
4. Verify row count, logical-key uniqueness, payload SHA and file SHA locally.
5. Upload data object under its immutable object key.
6. Read the object back from the permanent target, not from the local temp file.
7. Recompute compressed SHA, decompress, recompute canonical payload SHA and row count.
8. Upload manifest only after the data-object readback succeeds.
9. Read manifest back and verify it points to the exact data-object hashes.
10. Remove local temp data.

If an object already exists:

- same manifest + same hashes => idempotent success;
- any mismatch => `FAIL_CONFLICT`, no overwrite, no source change.

## 6. Restore drill

`ARCHIVE_WRITTEN` is not enough for deletion eligibility. At least one representative partition per table/label contract must pass a restore drill.

Restore drill V1:

1. download permanent data object + manifest into ephemeral isolated storage;
2. verify both hashes and schema;
3. load through `JsonlGzipPartitionSource`;
4. run an archive-backed real consumer;
5. while the source is still online, compare the exact consumer-relevant rowset/output with PostgreSQL;
6. record consumer name, row counts, output digest, object hashes, git SHA;
7. delete ephemeral restored files.

Do not restore into Production PostgreSQL for the drill.

## 7. Online retention policy is deliberately NOT fixed yet

Do not choose a 30/45/60/90-day retention window from capacity pressure alone.

Before freezing `ONLINE_RETENTION_DAYS`, measure all of the following per candidate table/label:

- active Production consumer maximum historical lookback;
- research consumer archive-readiness coverage;
- Forward milestone requirements;
- current/recent model retraining window requirements;
- late-arriving result/settlement corrections;
- monthly online bytes retained under 30 / 45 / 60 / 90-day scenarios;
- expected daily/monthly growth;
- Hobby <=5GB migration headroom after logical copy.

V1 deletion eligibility must use the most conservative required window across all consumers, plus an explicit safety buffer.

Until that review is complete:

`ONLINE_RETENTION_DAYS = UNDECIDED`

and no old odds/realtime rows are deletion-authorized by this document.

## 8. Protected data

Never remove from online storage merely because an archive copy exists when any of these applies:

- current active Production consumer still directly reads it;
- archive read-through consumer is not implemented/equivalent;
- current V4 / Stage2 / prospective Forward evidence requires it online;
- `learning_all` / FINAL previous-odds, drift, or steam coupling is unresolved;
- result/settlement correction window is unresolved;
- exact logical key/schema is ambiguous;
- no permanent-target restore drill exists;
- source-row inventory/hash changed after deletion approval.

`learning_all` remains protected under the current contract.

## 9. Deletion gate for one old partition

Even after permanent archival, a specific online partition may be deleted only after ALL gates pass:

1. permanent object + manifest exist;
2. permanent-target readback PASS;
3. restore drill PASS;
4. consumer coverage / zero-online-consumer proof for that exact old partition;
5. frozen online retention rule says partition is cold;
6. fresh source row count/date/key digest matches the archived manifest or a separately frozen deletion digest;
7. fresh Railway recovery point exists;
8. explicit user approval names the table/label/date partition;
9. bounded DELETE only; no unrelated table/index/schema mutation;
10. post-delete operational and archive-backed consumer verification PASS.

A plain DELETE is not expected to shrink the physical volume immediately. Do not use `VACUUM FULL` merely to make the graph smaller; Hobby migration should reclaim dead/free space naturally through logical migration into the fresh <=5GB target.

## 10. Current evidence as of 2026-09-15

Real Production-read-only pilots already passed in ephemeral runner storage:

- July `v2_odds_trifecta`: 588,156 rows, gzip 8,138,479 bytes, archive readback + per-race online equivalence PASS.
- July `v2_realtime_odds_snapshots`, `label=final_ab`: 335,680 rows / 2,848 races, gzip 9,350,371 bytes, archive-backed `analyze_final_ab_features_pg.py` + online value equivalence PASS.

These prove the file/read-through contract, not permanent durability. None of those archive files were retained outside the CI runner.

## 11. Next research-only step

Before any bucket creation or upload:

1. run a read-only retention-scenario audit for 30/45/60/90 days;
2. map remaining direct historical SQL consumers to archive-capable / online-required / obsolete;
3. estimate the fresh logical-migration size under each scenario;
4. then request explicit approval for creating the permanent bucket and credentials.

Final state of this document:

`TARGET_DESIGN_FROZEN / RAILWAY_BUCKET_PREFERRED / PERMANENT_UPLOAD_NOT_STARTED / ONLINE_RETENTION_UNDECIDED / DELETE_BLOCKED`
