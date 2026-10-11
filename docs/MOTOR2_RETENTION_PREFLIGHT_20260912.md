# Motor2 retention preflight — 2026-09-12 JST

Status: **read-only / no Production mutation**

## Retention contract

For historical `v2_v24_motor2_forward_shadow` rows in `run_class='final'` and `window_name='final'`:

- exclude the current JST date;
- require a race deadline;
- treat Motor2 shadow generations as sparse because the collector saves only candidate / probability-rank-boundary rows;
- for each race, choose the latest non-empty `snapshot_key` whose generation has no repeated ticket and whose last `snapshot_at` is at or before `deadline_at`;
- retain that chosen generation;
- classify other snapshot generations for that eligible race as retention candidates;
- if no valid pre-deadline generation exists, protect the entire race from cleanup.

## Production read-only result

GitHub Actions run: `34691924189`

- source table rows: **171,590**
- source relation bytes: **206,536,704**
- scoped historical FINAL rows: **91,259**
- scoped races: **2,632**
- snapshot generations: **5,157**
- pre-deadline generations: **4,718**
- eligible races with a retained pre-deadline generation: **2,615**
- protected races: **17**
- retained rows in chosen generations: **46,257**
- older/non-chosen candidate rows: **44,694**
- candidate share of scoped historical FINAL rows: **48.974896%**
- rows observed after deadline in the scope: **7,778**

The candidate rows are **26.046972%** of all rows currently in the Motor2 shadow table. A simple row-proportional estimate against the current 206,536,704-byte relation is about **53.8 MB (51.3 MiB)**. This is only a planning estimate; PostgreSQL tuple/index layout means physical reclaimed space will differ.

## Pre-delete archive

Artifact: `motor2-retention-predelete-34691924189`

- artifact ID: `10297234513`
- artifact ZIP bytes: `4,415,672`
- artifact ZIP SHA-256: `313641cbc0a9bd3aaeb1e9feafbe2313e6d810210a1c5f95474d192b961e5b03`
- archived retention candidate rows: **44,694**
- candidate ID SHA-256: `285e132025b4a87e6ee85cc05014f629f50e35b4f224f06b9927e98dba44bbb3`
- candidate content SHA-256: `046f38e1ebaaae1eaf4da9589ed1fb17a38927b9ccaa05e9f814e63a5285b477`
- candidate ID range: `27050..173234`
- candidate race-date range: `2026-08-20..2026-09-11`

The downloaded artifact was independently checked after CI. Its ZIP digest matched GitHub metadata, and decompressing `motor2_retention_candidate_rows.jsonl.gz` reproduced the same 44,694 rows and both candidate hashes.

## Safety

- `mutation_performed=false`
- Production connection was forced read-only through `PGOPTIONS` and `SET TRANSACTION READ ONLY`.
- No `DELETE`, `UPDATE`, schema change, index drop, or `VACUUM FULL` was executed.
- A future delete, if explicitly approved, must be bounded to the archived candidate IDs and must fail closed if the pre-delete count/hash no longer matches this archive.
- Normal PostgreSQL deletion makes pages reusable internally; it does not guarantee an immediate reduction in Railway `DISK_USAGE_GB`. `VACUUM FULL` is not part of this plan.
