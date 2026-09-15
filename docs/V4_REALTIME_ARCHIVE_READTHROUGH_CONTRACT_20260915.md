# V4 realtime archive read-through contract

Status: `RESEARCH_ONLY / NO_PRODUCTION_MUTATION / ARCHIVE_FIRST / NO_RETENTION_CUTOFF`

Date: 2026-09-15 JST

## Purpose

Define a safe ownership split for large realtime/history tables so that old timing-clean evidence can remain available for research and reproducibility without forcing all historical rows to stay in the live Railway PostgreSQL database.

This document does **not** authorize export, deletion, retention changes, schema changes, service/Cron changes, or Railway plan migration.

## Confirmed live-path dependency boundary

### Base trifecta odds

Key current-day paths are bounded to the target date / target race IDs.

- `run_daily_data_prepare_pg.py` audits the target date.
- `run_odds_window_pg.py` is invoked by the legacy morning/day/night window pipeline and operates on the active window.
- `v21_realtime_collector_pg.py::fetch_day_base()` reads `v2_odds_trifecta` only for the target day's race-id prefix.
- `v24_pre_candidate_notifier_pg.py` similarly uses target-day bounded race IDs.

Therefore the full multi-month `v2_odds_trifecta` history is not required merely to run the current-day live collector.

### Realtime odds drift / steam

`v21_realtime_collector_pg.py::_fetch_previous_odds(race_id)` reads only `v2_realtime_odds_snapshots` rows for the **same race_id**, ordered by `snapshot_at DESC`, and derives the latest prior row per ticket.

Important implication:

- live drift/steam computation requires earlier snapshots for the same active race;
- it does **not** require realtime-odds rows from old race IDs or old dates;
- old realtime odds history remains valuable for research/replay, but is not a direct live dependency for a different day's race.

### Realtime decision inputs

The current v22 decision path reads realtime snapshot tables by the active `race_date` and `snapshot_label` / target race scope. It does not need the entire historical realtime relation to score today's races.

This applies conceptually to:

- `v2_realtime_odds_snapshots`
- `v2_realtime_weather_snapshots`
- `v2_realtime_exhibition_snapshots`
- `v2_realtime_entry_snapshots`
- `v2_realtime_race_condition_snapshots`
- `v2_realtime_racer_condition_snapshots`

Historical rows are still required by research and Forward-evaluation utilities until those readers are migrated.

## Current Production entrypoints rechecked

Railway Production currently uses:

- `cron-data-prepare` -> `python -u run_daily_data_prepare_pg.py`
- `cron-window-morning/day/night` -> `python -u run_window_pipeline_pg.py`
- `cron-final-check` -> `python -u run_final_pg.py`
- `cron-learning-all` -> `python -u run_learning_all_realtime_pg.py`

`cron-learning-all` must **not** be stopped merely for storage reduction. Its same-race snapshots can become the previous-odds source used by FINAL, affecting drift/steam features.

## Consumer classification

### Class A — must remain online for live operation

Keep the active race/day slice required by current live collectors and decisions:

- today's/currently active race cards and entries;
- today's base odds fallback where required;
- same-race earlier realtime snapshots needed for previous-odds features;
- exact snapshot used for the final decision;
- timing-safe Stage2 evidence still owned by the current contract;
- current Forward provenance and settlement evidence required for active evaluation.

### Class B — historical research consumers; migrate to archive read-through

Default-branch research/validation code still assumes historical rows are directly queryable from PostgreSQL, including families such as:

- `analyze_*`
- `backtest_*`
- `compare_*`
- `feature_lab_*`
- walk-forward / OOS research
- historical odds-window analysis

Examples already confirmed include `feature_lab_pg.py`, `compare_motor_boat_ab_pg.py`, `backtest_n02_walkforward_pg.py`, `analyze_final_ab_features_pg*.py`, and other model/feature diagnostics.

These tools are the main reason old timing-clean data cannot simply be deleted. They should be migrated to a shared archive-access layer rather than each implementing its own historical file logic.

### Class C — maintenance / diagnostics; either archive-aware or retire

Examples include:

- `pg_backtest_ready_check.py`
- `run_historical_month_gap_repair_pg.py`
- historical repair / gap diagnostics
- data coverage and integrity checks

Each tool must be classified as either:

1. still useful and therefore made archive-aware; or
2. obsolete and explicitly retired after dependency review.

The presence of an old maintenance script alone must not force all historical rows to remain online forever.

### Evidence-sensitive `historical` snapshot label

Default-branch code confirms that `snapshot_label='historical'` is still consumed by multiple research and evidence workflows, including weather/wave profile analysis, candidate-feature research, historical data diagnostics and exhibition-ST Forward-shadow collection.

Therefore `historical` rows are **not** a blind-delete target.

They are, however, a strong archive-read-through pilot candidate because:

- the label represents historical/research evidence rather than today's live FINAL decision state;
- the consumers are identifiable and bounded;
- those consumers can be migrated one by one to a shared archive reader;
- exact PostgreSQL-vs-archive equality can be tested before any online row is removed.

The first archive pilot should preserve the `historical` label exactly and prove that at least one representative consumer returns identical rows/metrics from PostgreSQL and archive input.

Do not rename or collapse `historical` into another label because the label itself is part of the evidence contract in several scripts.

## Proposed read-through interface

Research code should stop hard-coding direct historical SQL against large live tables. A shared research-only adapter should expose logical operations such as:

- `load_base_trifecta_odds(race_ids | date_range)`
- `load_realtime_odds(race_ids | date_range, labels=None)`
- `load_realtime_exhibition(race_ids | date_range, labels=None)`
- `load_realtime_weather(race_ids | date_range, labels=None)`
- `load_realtime_conditions(race_ids | date_range, labels=None)`

Lookup order for **research jobs only**:

1. query the online PostgreSQL operational slice;
2. if requested historical dates are not online, load the verified archive partition;
3. fail closed if a required partition is missing, manifest validation fails, schema version is unsupported, or the requested evidence cannot be reproduced exactly.

The live PRE/FINAL purchase-decision path must not depend on external archive availability.

## Archive partition contract

A future export should be bounded by table + calendar month (or smaller chunks if needed). Each partition must record:

- source table name;
- schema / archive-contract version;
- exported column list and types;
- inclusive min/max race date;
- min/max race ID where applicable;
- exact row count;
- logical-key duplicate count;
- uncompressed canonical payload SHA-256;
- archived-file SHA-256;
- uncompressed/compressed byte sizes;
- export timestamp;
- source Production DB identity / migration batch ID;
- readback/restore verification result.

A deterministic canonical ordering must be used before hashing, based on each table's logical key, e.g.:

- base odds: `race_id, ticket`
- realtime odds: `race_id, snapshot_label, ticket`
- realtime exhibition/entry/racer-condition: `race_id, snapshot_label, lane`
- weather/race-condition: `race_id, snapshot_label`

No archive partition is eligible for online deletion until the canonical readback reproduces row count and key/value content.

## Data-format rule

No storage format is mandated yet. The selected format must preserve PostgreSQL numeric/timestamp/JSON semantics without lossy conversion and support bounded readback.

A simple first implementation may use deterministic database exports plus compression and a manifest; a columnar format may be adopted later only if exact round-trip equivalence is demonstrated.

Do not choose a format merely for maximum compression if it weakens restoration or auditability.

## First pilot scope

Before selecting a global retention boundary, use one old, completed calendar month as a read-only pilot.

Pilot requirements:

1. export only; do not delete source rows;
2. start with `snapshot_label='historical'` for the large realtime weather/exhibition/racer-condition families and, separately, a bounded old-month slice of base trifecta odds;
3. produce per-table manifests and SHA-256 hashes;
4. read the exported data back through the research adapter;
5. compare row counts, logical keys and representative research outputs with the original PostgreSQL query;
6. require zero logical differences;
7. retain the source rows online after the pilot until a later explicit Production removal approval.

A pilot month should be chosen only after confirming it is fully settled and not part of an active prospective evidence window.

## Online retention boundary

No arbitrary `N days` cutoff is authorized yet.

A future retention boundary may be proposed only after:

1. archive-aware research readers exist for the important historical consumers;
2. live-path tests prove current-day scoring does not query dates outside the online slice;
3. same-race previous-odds behavior is preserved exactly;
4. Stage2 / Challenger / Forward evidence retention requirements are explicitly mapped;
5. nightly settlement/evaluation completes before any source rows age out;
6. archive readback is tested on representative old months;
7. database growth/headroom is measured;
8. an exact proposed cutoff and reclaimable size are calculated;
9. the user explicitly approves the Production migration/removal.

## Migration sequence

1. Build the research-only archive reader abstraction.
2. Port one representative historical consumer and prove PostgreSQL-vs-archive equality.
3. Port the remaining high-value historical consumers.
4. Export one old month read-only; create manifest and hashes.
5. Perform readback/replay comparison with zero logical differences.
6. Expand bounded archive coverage month by month.
7. Re-run the active consumer scan.
8. Calculate exact online minimum set, daily growth, and Hobby headroom.
9. Obtain explicit approval for any Production deletion/migration.
10. Only then remove bounded old online partitions/rows and verify live + research behavior.

## Current decision

`OLD_REALTIME_HISTORY_NOT_DIRECT_LIVE_DEPENDENCY / SAME_RACE_PREVIOUS_ODDS_MUST_STAY_AVAILABLE_DURING_ACTIVE_RACE / HISTORICAL_LABEL_IS_EVIDENCE_SENSITIVE_BUT_ARCHIVEABLE_AFTER_EQUIVALENCE / HISTORICAL_RESEARCH_NEEDS_READ_THROUGH / NO_RETENTION_CUTOFF_YET / NO_DELETE / NO_SERVICE_CHANGE`
