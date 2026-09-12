# Historical realtime-label cold-archive contract

Date: 2026-09-12 JST
Status: **RESEARCH ONLY / NO ARCHIVE OR DELETE AUTHORIZED**
Parent research: PR #336 (`research/storage-retention-contract-20260912`)

## Purpose

Define the safety contract that would have to exist before any future attempt to move completed `snapshot_label='historical'` realtime rows out of the hot Production PostgreSQL database.

This document is not an implementation plan and does not authorize:

- DELETE / UPDATE / TRUNCATE;
- VACUUM / VACUUM FULL / physical rewrite;
- schema/index change;
- backup creation or restore;
- Railway Variable/Cron/service/volume change;
- model or threshold change;
- LINE behavior change;
- Forward persistence change;
- purchase behavior.

Current gate:

`HISTORICAL_LABEL_PRESERVE_BY_DEFAULT / NO_CURRENT_STEADY_STATE_PRODUCTION_READ_DEPENDENCY_CONFIRMED_BY_STATIC_RUNTIME_CLASSIFICATION / RESEARCH_AND_REPAIR_CONSUMERS_EXIST / EXTERNAL_ARCHIVE_TARGET_UNDEFINED / RESTORE_PATH_UNVERIFIED / FRESH_BACKUP_REQUIRED / NO_DELETE_AUTHORIZED`

## 1. Scope

The term **historical label** in this contract refers to completed historical rows in realtime snapshot tables such as:

- `v2_realtime_weather_snapshots`
- `v2_realtime_exhibition_snapshots`
- `v2_realtime_race_condition_snapshots`
- `v2_realtime_racer_condition_snapshots`
- related historical beforeinfo-derived snapshot data where `snapshot_label='historical'`

This contract does not cover:

- current `final_ab` rows;
- current `learning_all` rows;
- base `v2_odds_trifecta` history;
- Motor2 retention candidates;
- Racer Course / Opponent Pressure data;
- results, entries, races, or other core history.

Those require separate contracts.

## 2. Static runtime classification completed on 2026-09-12

### A. Production final pipeline

`v25_final_realtime_pipeline_pg.py` contains an optional Wave venue/lane Shadow path:

- `RUN_WAVE_VL_FINAL_SHADOW` defaults to `0`;
- only when explicitly enabled does it call `collect_wave_venue_lane_final_shadow_pg.py`;
- that collector imports `wave_venue_lane_profile_pg.py`, whose profile build reads historical weather snapshots.

Current Railway `cron-final-check` variable names were read-only inspected. They include:

- `RUN_MOTOR2_FINAL_SHADOW`
- `RUN_N02_WINDLT4_SHADOW`

but do **not** include `RUN_WAVE_VL_FINAL_SHADOW`.

Therefore the optional Wave historical-profile path is not currently enabled in the steady-state Production FINAL service. It remains a latent/optional dependency and must be rechecked immediately before any future archive request.

### B. Exhibition ST Forward scheduled collector

`collect_exhibition_st_forward_shadow_pg.py` contains a stored-historical read path, but only under the dry-run/past replay combination.

The active scheduled workflow `.github/workflows/exhibition-st-forward-scheduled-collector.yml` explicitly sets:

- `EXH_ST_FORWARD_ENABLED='1'`
- `EXH_ST_FORWARD_DRY_RUN='0'`
- `EXH_ST_FORWARD_ALLOW_PAST_DRY_RUN='0'`
- `EXH_ST_FORWARD_DRYRUN_STORED_HISTORICAL='0'`

Thus the scheduled collector uses fresh official beforeinfo and does not require historical stored rows in its normal scheduled path.

The manual/dry-run workflow can intentionally enable historical replay. That is a research/validation dependency, not a steady-state live runtime dependency.

### C. Historical diagnostics

`.github/workflows/railway-historical-data-diagnostics.yml` has:

- `workflow_dispatch`
- owner-only issue-comment commands

and no schedule trigger.

It is an on-demand diagnostic consumer, not a steady-state Production runtime dependency.

### D. Outage repair / backfill

`.github/workflows/railway-outage-gap-repair-20260828-30.yml` is owner-command gated and explicitly asserts that its trigger block contains neither `schedule:` nor `workflow_dispatch:`.

It is maintenance/repair tooling. It can read or create historical-labeled beforeinfo, but it is not part of the regular PRE/FINAL/nightly runtime.

`run_historical_month_gap_repair_pg.py` has no repository workflow reference found in the static search performed for this classification. Treat it as maintenance/manual tooling unless future runtime linkage is discovered.

### E. Research / analysis consumers

The repository classification explicitly places `analyze_*`, historical OOS, walk-forward, feature, and calibration scripts in Research/validation class C unless directly promoted.

Known historical-label consumers include research scripts such as:

- `analyze_candidate_rules_features_pg.py`
- `analyze_candidate_feature_filters_phase6_pg.py`
- `analyze_candidate_feature_filters_phase6_oos_pg.py`
- related N02 / candidate-filter / historical OOS analysis

These consumers are important and must continue to be supported, but they do not require the data to remain permanently in the hot Production database if a tested restore-before-research workflow exists.

### F. Core Production entrypoints

No direct `snapshot_label='historical'` read was found in the current core Production entrypoints checked for this contract, including:

- `run_window_pipeline_pg.py`
- `v25_final_realtime_pipeline_pg.py` itself
- `run_nightly_results_pg.py`

The only relevant indirect FINAL path identified is the optional Wave Shadow described above, and it is currently default-off and not enabled by the active `cron-final-check` Railway variable set.

## 3. Classification result

Current static evidence supports this conclusion:

**There is no confirmed steady-state Production read dependency requiring completed historical-labeled realtime rows to remain permanently hot in PostgreSQL today.**

However, the rows are still required by:

1. research/OOS/feature analysis;
2. manual diagnostics;
3. outage repair/backfill validation;
4. explicit historical replay modes;
5. any future re-enablement of the Wave venue/lane Shadow or other new consumer.

Therefore the current policy remains **preserve by default** until an archive + restore system is proven.

## 4. Cold-archive prerequisites

No row may be removed from hot PostgreSQL until every prerequisite below is satisfied.

### Gate A — archive format is defined

A canonical, lossless format must be specified for each archived table, preserving at minimum:

- table name;
- complete row payload needed by consumers;
- primary/business keys;
- `race_id`;
- `race_date` where present;
- `snapshot_label`;
- lane where present;
- source timestamps / created timestamps needed for provenance;
- exact type/NULL semantics required to reconstruct the rows.

CSV may be acceptable only if type/NULL/timezone fidelity is demonstrated. A database-native or strongly typed format is preferable if available.

### Gate B — archive location is defined

The external archive target must be named and have documented:

- ownership;
- retention period;
- access controls;
- cost;
- durability expectation;
- how it is kept separate from the constrained Railway 5 GB Production volume.

At the time of this contract, no approved archive target is defined.

### Gate C — immutable manifest

Each archive batch must have a manifest containing at least:

- table;
- date/race-id range;
- row count;
- minimum/maximum key/date values;
- content digest (for example SHA-256 over a canonical export representation);
- export timestamp;
- archive object/path identifier;
- source Production snapshot/backup identifier where available.

The manifest must be stored separately enough that archive loss/corruption can be detected.

### Gate D — restore-before-research path

A documented restore process must recreate the archived dataset into an isolated research/restoration target without altering current Production data.

Before Production deletion is even requested, a representative archive must be restored and verified with:

- exact row-count match;
- key uniqueness/integrity checks;
- manifest digest verification or equivalent content check;
- known historical research consumer smoke tests;
- no LINE / purchase / Production model path;
- no accidental writes back to current Production.

### Gate E — active runtime dependency recheck

Immediately before any archive/delete request, re-run static and Railway configuration checks.

At minimum re-confirm:

- `RUN_WAVE_VL_FINAL_SHADOW` is absent/false unless the archive restore path is integrated for it;
- scheduled Exhibition ST Forward still has `DRYRUN_STORED_HISTORICAL=0` in its live schedule;
- no new PRE/FINAL/nightly consumer reads historical label;
- no new Railway service/start command depends on historical-labeled rows;
- no new scheduled GitHub Action requires them.

Any new steady-state runtime dependency blocks deletion until adapted and validated.

### Gate F — fresh Production recovery point

A fresh restorable Production backup/restore point must exist immediately before the first destructive archive cleanup.

The existing `Pre-Security-Patch Backup` from 2026-08-23 is too old to satisfy this gate.

Backup creation/restore testing is itself a Production operation requiring separate explicit approval.

### Gate G — explicit Production delete approval

Archive creation, validation, and this contract do not authorize deleting source rows.

Any actual Production `DELETE`, partition removal, table rewrite, or other source-data removal must be presented separately with:

- exact tables;
- exact date/race ranges;
- exact row counts;
- exact manifest/digest identifiers;
- restore proof;
- fresh backup proof;
- expected logical and physical capacity effect;
- rollback/recovery procedure;
- explicit user approval.

## 5. First-write preservation rule

No source deletion may occur until the archive copy has been fully written, closed/finalized, verified, and independently readable.

The process must be:

1. read source;
2. write external archive;
3. compute and persist manifest;
4. re-read archive;
5. verify counts/digests/keys;
6. run representative restore test;
7. obtain fresh Production recovery point;
8. request separate explicit deletion approval;
9. only after approval, perform bounded source cleanup.

Never stream-delete while exporting.

## 6. Research restore contract

Historical research must never silently fall back to incomplete hot data after archiving.

A future research runner must either:

- prove required range is still present hot; or
- explicitly restore/load the required archive range first; or
- fail closed with a clear `HISTORICAL_ARCHIVE_REQUIRED`-type result.

It must not treat missing historical rows as zeros/defaults or continue with a partial historical sample without an explicit research mode that acknowledges incompleteness.

## 7. Capacity expectations

Historical archival is a long-term data-placement option, not an immediate guaranteed Railway-volume reduction mechanism.

Important distinctions:

- deleting rows may free PostgreSQL pages for internal reuse but may not proportionally reduce Railway volume usage;
- ordinary VACUUM does not guarantee filesystem shrink;
- `VACUUM FULL` / table rewrite is a separate high-impact Production operation requiring separate approval;
- index and table physical behavior must be measured, not assumed.

Therefore any future archive proposal must report both:

- logical rows/tuple bytes removed from the hot working set; and
- observed physical Railway/PostgreSQL relation-size effect after the approved operation.

## 8. Archive boundary recommendation

Do not define a deletion date boundary yet.

A future boundary should be based on all of:

- completed race dates only;
- no unresolved outage repair window;
- no pending research needing hot access;
- archive/restore verification coverage;
- sufficient recent hot-history window for operations and common analyses;
- capacity pressure at that time.

No fixed “keep N days” rule is authorized by this document.

## 9. Explicit preserves

Until all gates pass, preserve all current historical-labeled rows.

Even after a future archive system exists, preserve hot data required by any active Production path or unresolved repair operation.

Do not combine historical-label archival with:

- `learning_all` cleanup;
- `v2_odds_trifecta` cleanup;
- Motor2 cleanup;
- index dropping;
- model promotion;
- threshold changes.

Each has a separate risk model and approval boundary.

## 10. Abort conditions

Abort any future archive cleanup if:

- external archive target is unavailable or undefined;
- manifest verification fails;
- restored row count/digest differs;
- representative research consumer fails on restored data;
- a current runtime dependency is discovered;
- fresh backup/recovery point is missing;
- Production database health is degraded;
- deletion candidate range/count cannot be frozen exactly;
- user approval does not explicitly cover the destructive step.

## 11. Current decision

The static classification is sufficient to continue **researching cold archival**, but not sufficient to remove a single Production row.

Current decision:

**`COLD_ARCHIVE_CONTRACT_READY_FOR_FURTHER_RESEARCH / NO_ARCHIVE_TARGET / NO_RESTORE_PROOF / NO_DELETE_AUTHORIZED`**
