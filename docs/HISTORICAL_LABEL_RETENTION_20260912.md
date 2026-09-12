# Historical realtime-label retention review — 2026-09-12

Research-only capacity note. No Production DB mutation, export, archive, Railway change, model change, LINE action, or purchase action is authorized by this document.

## Exact read-only inventory

`Storage Historical Label Readonly` ran against Production with PostgreSQL default-transaction read-only mode.

| table | historical rows | races | date range | logical tuple bytes | whole relation bytes |
|---|---:|---:|---|---:|---:|
| `v2_realtime_weather_snapshots` | 63,468 | 63,468 | 2025-07-01..2026-08-30 | 128,006,008 | 193,069,056 |
| `v2_realtime_exhibition_snapshots` | 373,230 | 62,205 | 2025-07-01..2026-08-30 | 76,587,872 | 137,428,992 |
| `v2_realtime_race_condition_snapshots` | 63,468 | 63,468 | 2025-07-01..2026-08-30 | 128,478,648 | 174,718,976 |
| `v2_realtime_racer_condition_snapshots` | 380,808 | 63,468 | 2025-07-01..2026-08-30 | 133,416,088 | 199,688,192 |
| **total** | **880,974** | — | — | **466,488,616** | **704,905,216** |

The 466.5 MB figure is logical tuple payload, **not guaranteed physical Railway-volume reclaim**. Whole-relation bytes include non-historical labels and indexes, so 704.9 MB is also not a deletion estimate.

## Dependency classification

### Current Production PRE / FINAL

No evidence was found that the main current PRE/FINAL entrypoints require the stored `historical` label as their normal live input. Current live collection uses window/realtime sources.

This is not enough to classify the rows as disposable because research, Shadow and repair code still reads them explicitly.

### Active Forward / Shadow

The scheduled Exhibition-ST Forward collector normally fetches fresh official beforeinfo in its timing window. Its stored-`historical` read path is gated to dry-run + explicit past-replay flags, and the scheduled workflow sets that path OFF.

Other research/Shadow code still uses historical-labelled rows for replay/profile/evaluation work, including wave/venue-lane and historical feature studies.

### Repair / diagnostics

Historical beforeinfo backfill/repair and outage diagnostics explicitly create or inspect `snapshot_label='historical'` rows. These are repair/reconstruction tools rather than the current PRE/FINAL live path.

### Analysis / OOS

Multiple analysis files explicitly select `historical` first or exclusively for weather/exhibition/racer-condition features. Removing the rows would make those studies non-reproducible unless a replacement archive/restore contract exists.

## Railway service-name finding

Service names are not dependency evidence:

- `historical-backfill` currently runs `diagnose_motor2_parser_pg.py`, a read-only Motor2 parser diagnostic.
- `backtest-analysis` currently runs `collect_v24_motor2_forward_shadow_pg.py` monthly.

Therefore no storage decision should be based only on Railway service names.

## Retention decision

Current gate:

`HISTORICAL_LABEL_LARGE_466MB_LOGICAL / NOT_CURRENT_MAIN_PRE_FINAL_INPUT / ACTIVE_RESEARCH_REPLAY_DEPENDENCIES / REPAIR_DEPENDENCIES / REPRODUCIBILITY_VALUE / NO_DELETE_CONTRACT / COLD_ARCHIVE_RESEARCH_ONLY`

Policy for now:

1. Preserve all existing historical-labelled rows.
2. Do not delete, VACUUM, rewrite, or move them from Production without a separate approved archive/restore design.
3. A future cold-archive proposal must prove that current Production PRE/FINAL remains independent, identify every scheduled/manual research consumer, provide deterministic restore/checksum evidence, and state the real physical reclaim method.
4. Do not count logical tuple bytes as guaranteed Railway volume reduction.
