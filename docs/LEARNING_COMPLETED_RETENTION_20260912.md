# Completed `learning_all` retention review — 2026-09-12

Research-only capacity note. No DELETE, archive/export, schema change, VACUUM, Railway/Cron change, model change, LINE change, or purchase action is authorized by this document.

## Why this is different from stopping `cron-learning-all`

Stopping live `learning_all` collection is blocked because its odds row can become the immediate previous market observation used by a later `final_ab` snapshot. That can change drift/steam features and Production v22 score.

Completed race IDs are a different retention question. Once a race is finished, its stored `learning_all` rows are no longer needed for **future live collection of that race ID**. They still have research, replay, audit and reproducibility value, so this does not make them disposable.

## Exact completed inventory

Production read-only audit, `race_date < current_date`:

- completed learning rows: **451,818**
- completed learning logical tuple bytes: **101,044,256**
- rows with matching `final_ab` identity: **450,666**
- direct learning-only rows across the six realtime tables: **1,152**
- date span: 2026-08-16..2026-09-11

Recent seven completed dates contribute **17,005,616 logical bytes**, or **2,429,373.71 logical bytes/day** on average.

A hypothetical seven-completed-day hot window would currently place about **84,038,640 logical bytes / 375,583 rows** outside the hot window. This is a logical-data estimate only, not a physical Railway-volume reclaim estimate.

## Consumer finding

Repository search found no current Production consumer with a literal `snapshot_label='learning_all'` read. Live Production coupling instead occurs indirectly through the collector's cross-label previous-odds lookup while the race is active.

Generic research/analysis tools can read realtime snapshot labels by parameter, and historical learning-vs-final evidence is useful for the current storage/feature audits. Therefore deleting completed learning rows without an archive/restore contract would reduce reproducibility even if future live scoring for completed race IDs is unaffected.

## Capacity significance

If a future archive/retention design could safely bound completed learning history while keeping current-day rows untouched, the measured recurring logical growth addressed would be about **2.43 MB/day**.

Combined with the conservative Motor2 retention candidate (~1.97 MB/day logical), these two research directions address about **28.7% of the measured logical growth across the ten tracked active tables**. This is prioritization evidence, not a physical disk forecast.

## Required design before any mutation

A future completed-learning retention proposal must provide all of the following:

1. Keep all current-day / active-race `learning_all` rows intact.
2. Prove that the retention boundary cannot remove a row while a later `final_ab` collection may still occur for that race.
3. Define a reproducible cold archive format for all six realtime tables, preserving identity, label, timestamps and feature payloads.
4. Provide archive checksums, row counts and deterministic restore verification before any source deletion.
5. Preserve enough hot history for current diagnostics and comparison workflows; seven completed days is only a measurement scenario, not an approved policy.
6. Re-run live previous-odds coupling audits before any mutation.
7. Require a fresh restorable backup and separate explicit approval for archive writes, DELETE and any VACUUM.
8. Never represent logical bytes as guaranteed Railway-volume shrink.

## Current decision

`LIVE_COLLECTION_MUST_CONTINUE / COMPLETED_RACE_LIVE_DEPENDENCY_ENDED / 101MB_LOGICAL_COMPLETED / 2.43MB_PER_DAY_RECENT_GROWTH / RESEARCH_REPRODUCIBILITY_DEPENDENCY / COLD_ARCHIVE_CONTRACT_MISSING / NO_DELETE_AUTHORIZED / NO_ARCHIVE_WRITE_AUTHORIZED / NO_CRON_CHANGE_AUTHORIZED`
