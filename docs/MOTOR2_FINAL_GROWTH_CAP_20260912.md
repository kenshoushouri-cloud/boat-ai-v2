# Motor2 FINAL Shadow growth-cap proposal — 2026-09-12

Status: **research-only / no Production activation**

## Problem

`cron-final-check` runs every 15 minutes during the live window. The current FINAL pipeline constructs `MOTOR2_SHADOW_SNAPSHOT_KEY` with the current clock time. The Motor2 table unique key is `(race_id, ticket, run_class, window_name, snapshot_key)`, so a repeated FINAL observation of the same race/ticket normally creates another logical row instead of replacing the previous FINAL row.

Read-only storage work has already identified Motor2 Forward Shadow as the largest tracked daily logical-growth contributor, at roughly 6 MiB/day in the prior seven-day attribution window. The existing retention audit also found a conservative set of older `final/final` rows that could hypothetically be removed while the protected Performance, Robustness and latest PRE health outputs remained zero-diff. That evidence supports testing a prevention strategy for future FINAL growth rather than relying on later deletion.

## Proposed future opt-in mode

Research name: `latest_per_race`.

The proposed key for FINAL Motor2 observations is stable within a race date:

`YYYYMMDD_final_latest`

The existing unique key already contains `race_id` and `ticket`. Therefore repeated FINAL collection for the same race/ticket would update that row, while different races/tickets remain separate.

The effect is to retain the latest FINAL Motor2 state for each race/ticket instead of accumulating one row for each 15-minute invocation.

## What this does NOT change

This proposal does not change:

- v24/v22 Production BUY/WATCH/SKIP logic;
- Racer Course coefficient;
- Opponent Pressure coefficient;
- current odds collection cadence;
- LINE behavior;
- Forward decision persistence;
- purchase behavior;
- historical rows already stored;
- PRE Motor2 health snapshots;
- current Production configuration.

The current behavior remains the default in the pure research contract (`timestamped`). No Production code is wired to the compact mode in this Draft.

## Why prevention is safer than cleanup

The current Hobby plan cannot create a fresh Railway Volume Backup. Large DELETE/VACUUM/rewrite operations therefore have an unfavorable recovery profile. Preventing redundant future growth is preferable to deleting large amounts of existing data.

This mode would also avoid relying on `VACUUM FULL` for physical reclamation. It limits future logical allocation instead.

## Required evidence before any Production proposal

Before runtime wiring or activation, all of the following are required:

1. static proof that FINAL Motor2 Shadow is observational and cannot alter Production decisions/LINE;
2. confirm current reports/evaluators do not require multiple intra-window FINAL snapshots for any protected operational output;
3. replay the existing retention contract against a representative period and prove the latest-per-race projection preserves protected outputs;
4. quantify projected row/byte reduction from natural FINAL cadence;
5. fail-closed default: timestamped behavior unless an explicit new variable is enabled;
6. no change to PRE retention/health behavior;
7. explicit Production approval before merge/runtime variable/Cron behavior changes.

## Learning-all finding

`learning_all` cannot simply be disabled for capacity. The cross-label previous-odds lookup means learning odds can become the predecessor for later `final_ab` drift/steam features. A full pause is therefore model-input semantic change, not storage-neutral maintenance.

The narrower PR #337 odds-only learning design remains a secondary candidate. Its estimated logical savings are much smaller (~0.62 MiB/day of recent non-odds payload), although it can also reduce duplicated HTTP/parsing/write work.

## Current ordering

1. Motor2 FINAL future-growth cap — strongest prevention candidate, research only.
2. Odds-only `learning_all` — smaller capacity reduction, preserves odds cadence.
3. Realtime odds — preserve both labels for now because of Production movement-feature coupling.
4. Historical cleanup/index removal — defer while no fresh recovery point is available.

Current gate:

`RESEARCH_ONLY / DEFAULT_TIMESTAMPED / NO_RUNTIME_WIRING / NO_PRODUCTION_CHANGE / NO_DELETE / NO_VACUUM / NO_INDEX_DROP / EXPLICIT_APPROVAL_REQUIRED_FOR_ACTIVATION`
