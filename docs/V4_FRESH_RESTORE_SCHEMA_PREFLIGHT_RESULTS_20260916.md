# V4 fresh restore schema preflight results — 2026-09-16

Status: `PRODUCTION_READ_ONLY / CATALOG_ONLY / NO_ROW_COPY / NO_RETENTION_DECISION / NO_MUTATION`

Workflow run: `34987507242` (`Research fresh restore schema preflight production read-only`).

The audit used `default_transaction_read_only=on` and read PostgreSQL catalog/schema metadata plus relation sizes only. It did not copy table rows, change retention, export data, create a target database, or modify Railway Production.

## Database baseline

- PostgreSQL database bytes: `3,887,060,671`
- public user tables: `37`
- summed public user relation bytes: `3,876,478,976`
- summed heap bytes: `2,438,299,648`
- summed index bytes: `1,338,007,552`

The database-size number and sum-of-user-relations are close but are not interchangeable. Neither is a fresh-Hobby restore measurement.

## Largest current relations

| table | total bytes | heap bytes | index bytes |
|---|---:|---:|---:|
| `v2_odds_trifecta` | 1,844,002,816 | 977,633,280 | 866,066,432 |
| `v2_realtime_odds_snapshots` | 536,854,528 | 325,320,704 | 211,410,944 |
| `v2_result_entries` | 233,570,304 | 204,963,840 | 28,516,352 |
| `v2_v24_motor2_forward_shadow` | 219,717,632 | 174,055,424 | 45,580,288 |
| `v2_realtime_racer_condition_snapshots` | 203,825,152 | 168,869,888 | 34,881,536 |
| `v2_realtime_weather_snapshots` | 196,198,400 | 142,917,632 | 8,454,144 |
| `v2_realtime_race_condition_snapshots` | 178,159,616 | 118,784,000 | 5,693,440 |
| `v2_race_entries` | 139,837,440 | 93,765,632 | 46,014,464 |
| `v2_realtime_exhibition_snapshots` | 139,657,216 | 91,807,744 | 47,792,128 |
| `v2_racer_course_stats_snapshots` | 54,247,424 | 38,887,424 | 15,310,848 |
| `v2_results` | 33,267,712 | 28,524,544 | 4,702,208 |
| `v2_realtime_entry_snapshots` | 24,559,616 | 16,130,048 | 8,388,608 |
| `v2_races` | 18,841,600 | 13,459,456 | 5,341,184 |

## Storage concentration

The seven large base/realtime raw-evidence relations:

- `v2_odds_trifecta`
- `v2_realtime_odds_snapshots`
- `v2_realtime_racer_condition_snapshots`
- `v2_realtime_weather_snapshots`
- `v2_realtime_race_condition_snapshots`
- `v2_realtime_exhibition_snapshots`
- `v2_realtime_entry_snapshots`

currently sum to `3,123,257,344` relation bytes, about **80.57%** of all public user-relation bytes.

This is a structural planning result only. It does **not** mean 80.57% is deletable or that moving rows would reclaim the same percentage on the current volume. It confirms that small legacy bookkeeping tables cannot by themselves solve the Hobby migration problem.

For comparison, the clearly shared/core operational relations `v2_result_entries`, `v2_race_entries`, `v2_racer_course_stats_snapshots`, `v2_results`, `v2_races`, and `v2_opponent_pressure_shadow_v2` together account for about `481,435,648` relation bytes before considering other protected Forward/shadow evidence. These are not proposed deletion targets.

## Retention-key readiness

The catalog preflight found date/time/race/label retention-hint columns on every user table except tiny `pg_health_check`. Important archive-heavy relations expose explicit bounded keys such as `race_date`, `race_id`, `snapshot_label`, and/or `snapshot_at`, which supports deterministic partition planning.

This does not freeze a retention period. `ONLINE_RETENTION_DAYS` remains `UNDECIDED`.

## Implication for fresh restore work

The next useful read-only measurement is not another whole-database size check. It is a label/date hot-vs-cold matrix for the non-odds realtime snapshot families, followed by a retained-set logical restore rehearsal only after a conservative online-retention contract is frozen.

A future Hobby-fit claim must still be based on:

`FRESH_RESTORE_OBSERVED_SIZE + FROZEN_REQUIRED_HEADROOM <= 5GB`

and not on current relation bytes, tuple payload bytes, or expected DELETE reclaim.

## Current gate

`CATALOG_PREFLIGHT_PASS / USER_RELATIONS_3_876GB / RAW_EVIDENCE_FAMILIES_80_57PCT_OF_RELATION_BYTES / RETENTION_KEYS_PRESENT / ONLINE_RETENTION_UNDECIDED / NO_ROW_COPY / NO_DELETE / HOBBY_FIT_NOT_PROVEN`
