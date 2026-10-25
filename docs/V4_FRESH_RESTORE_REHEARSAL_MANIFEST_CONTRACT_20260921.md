# V4 fresh restore rehearsal manifest contract — 2026-09-21

Status: `RESEARCH_ONLY / PURE_OFFLINE / NON_PRODUCTION_ONLY / NO_ROW_COPY_YET / NO_PRODUCTION_MUTATION`

## Purpose

This contract prevents the project from jumping from read-only footprint analysis directly into a retained-set restore before the inputs are decision-grade.

A future fresh restore rehearsal is useful only if it measures a **frozen candidate retained set** with production-equivalent schema/indexes and an already-defined headroom policy. Running a copy before those boundaries exist would create a misleading Hobby-readiness number.

The pure gate is implemented in:

- `research/fresh_restore_rehearsal_manifest.py`
- `tests/test_fresh_restore_rehearsal_manifest.py`
- `.github/workflows/research-fresh-restore-rehearsal-manifest.yml`

It performs no database/network/Railway/archive operation.

## Required manifest

Contract:

`v4_fresh_restore_rehearsal_manifest_v1`

A PASS requires all of the following.

### Source

- exact 40-hex main SHA;
- Production source explicitly read-only;
- destructive source operations explicitly false.

### Target

- non-Production;
- ephemeral;
- explicit PostgreSQL major version.

The first decision-grade rehearsal must not create or mutate a Railway Production service/volume.

### Frozen online retention

The manifest must list every retained table once.

Modes:

- `keep_all`
- `bounded`

A bounded table requires a human-readable frozen boundary plus a SHA-256 computed over the exact UTF-8 boundary string. The gate recomputes that digest and rejects any mismatch, so the retained-set boundary cannot be edited without changing its identity.

Protected evidence tables must be explicitly listed and must remain present in the retained-set manifest. Capacity pressure is not a reason to silently exclude Forward/provenance/result evidence.

### Archive and recovery

Before any cold partition may be excluded from the fresh PostgreSQL target:

- the primary archive must be verified;
- an independent second recovery layer must be verified;
- each excluded partition must have a manifest SHA-256.

This gate intentionally remains stricter than a single Bucket copy.

### Schema identity

Freeze:

- schema SHA-256;
- migration script SHA-256;
- indexes/constraints/extensions identity.

A restore without production-equivalent indexes is not a Hobby-size proof.

### Headroom

Railway official documentation labels the Hobby volume limit as 5GB but does not define byte semantics in the referenced plan/volume pages. To avoid overstating capacity, this preregistration uses a conservative ceiling of exactly `5,000,000,000` bytes unless a future authoritative platform response provides an exact lower byte limit.

Before rehearsal, freeze:

- required reserve bytes;
- measured daily growth bytes;
- growth horizon days.

The reserve must cover at least the measured growth horizon. The post-restore acceptance decision remains a separate check:

`OBSERVED_FRESH_RESTORE_SIZE + REQUIRED_RESERVE <= 5,000,000,000 bytes`

A PASS from this manifest gate means only that the **rehearsal prerequisites** are frozen. It does not mean Hobby fit is proven.

## Current project state

As of 2026-09-21 the real project does **not** satisfy this PASS manifest:

- candidate-shadow zero-consumer is not reached;
- permanent archive is not created and verified;
- independent second recovery layer is not proven;
- final online retention boundary is not frozen;
- fresh retained-set restore has not been completed;
- required headroom policy is not frozen.

Therefore the correct current classification remains:

`REHEARSAL_PREREQUISITES_NOT_READY / HOBBY_READY_NOW_FALSE / OCT03_GO_NO_GO_NOT_FORCED_CUTOVER`

## Non-implications

This Draft does not authorize:

- Production row copy/write/delete;
- schema/VACUUM;
- Railway service/volume/plan changes;
- archive upload;
- retention cutoff selection;
- Production migration.

`purchase_action=false` remains unchanged.
