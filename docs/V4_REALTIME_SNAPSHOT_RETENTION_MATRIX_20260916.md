# V4 non-odds realtime snapshot retention matrix — 2026-09-16

Status: `PRODUCTION_READ_ONLY / LOGICAL_PAYLOAD_REFERENCE_ONLY / NO_RETENTION_CUTOFF / NO_DELETE`

Workflow run: `34987798420` (`Research realtime snapshot retention matrix production read-only`).

The run used `default_transaction_read_only=on` against Railway Production and measured label/date row counts plus `pg_column_size` logical payload for five non-odds realtime snapshot tables. It did not export row contents, mutate PostgreSQL, create an archive, or change Railway.

Reference date is `2026-09-15`; windows shown are planning scenarios only.

## Relation footprint of the five tables

| table | relation bytes |
|---|---:|
| `v2_realtime_racer_condition_snapshots` | 203,825,152 |
| `v2_realtime_weather_snapshots` | 196,198,400 |
| `v2_realtime_race_condition_snapshots` | 178,159,616 |
| `v2_realtime_exhibition_snapshots` | 139,657,216 |
| `v2_realtime_entry_snapshots` | 24,559,616 |
| **total** | **742,400,000** |

Relation bytes are current physical PostgreSQL relation sizes and must not be projected linearly from logical cold payload.

## 30-day reference — cold logical payload

Across these five tables, rows outside the 30-day reference window total approximately **497,868,776 logical payload bytes**.

Breakdown by snapshot label:

- `historical`: **463,043,016 bytes**
- `final_ab`: **33,476,400 bytes**
- `learning_all`: **1,344,344 bytes**
- `final_ab_debug`: **5,016 bytes**

The historical label dominates the old logical payload. This reinforces archive-first handling of historical evidence and shows that disabling/deleting `learning_all` is not a meaningful capacity lever here, in addition to its already-proven semantic coupling to FINAL previous-odds/drift/steam behavior.

## 60-day reference — cold logical payload

Across the same tables, rows outside the 60-day reference window total approximately **436,216,944 logical payload bytes**:

- `historical`: **428,761,888 bytes**
- `final_ab`: **7,450,040 bytes**
- `learning_all`: `0`
- debug residue: **5,016 bytes**

Again, this is not an approved 60-day cutoff.

## Table-level observations

### Racer condition

- relation: `203,825,152` bytes
- historical total: `380,808` rows / `133,416,088` logical bytes
- historical 30-day-cold: `378,000` rows / `132,430,208` bytes
- final_ab 30-day-cold: `22,806` rows / `7,525,896` bytes
- learning_all 30-day-cold: only `1,152` rows / `376,640` bytes

### Weather

- relation: `196,198,400` bytes
- historical total: `63,468` rows / `128,006,008` logical bytes
- historical 30-day-cold: `63,000` rows / `127,061,912` bytes
- final_ab 30-day-cold: `4,839` rows / `9,482,208` bytes
- learning_all 30-day-cold: `192` rows / `369,048` bytes

### Race condition

- relation: `178,159,616` bytes
- historical total: `63,468` rows / `128,478,648` logical bytes
- historical 30-day-cold: `63,000` rows / `127,531,864` bytes
- final_ab 30-day-cold: `3,801` rows / `7,425,448` bytes
- learning_all 30-day-cold: `192` rows / `370,584` bytes

### Exhibition

- relation: `139,657,216` bytes
- historical total: `373,230` rows / `76,587,872` logical bytes
- historical 30-day-cold: `370,458` rows / `76,019,032` bytes
- final_ab 30-day-cold: `15,090` rows / `3,291,576` bytes
- learning_all 30-day-cold: `84` rows / `16,104` bytes

### Entry

- relation: `24,559,616` bytes
- no `historical` label rows were present in this table in the measured Production state
- final_ab 30-day-cold: `29,034` rows / `5,751,272` bytes
- learning_all 30-day-cold: `1,152` rows / `211,968` bytes

## Migration interpretation

This matrix narrows the next fresh-restore work:

1. historical-label rows in non-odds realtime tables are the primary non-odds archive candidate family, subject to already-defined archive equivalence, permanent durability, restore, and zero-consumer gates;
2. old `final_ab` rows may also matter, but must preserve all active/research semantics and cannot be treated as equivalent to historical-label rows automatically;
3. `learning_all` remains protected and offers very little 30-day-cold logical payload in these five tables, so capacity pressure is not a reason to change its behavior;
4. current-day/hot data must remain online for active acquisition/scoring paths;
5. a fresh logical restore is still required to measure actual compact relation/index size after a retained-set copy.

Neither `30` nor `60` days is approved as `ONLINE_RETENTION_DAYS`.

## Current gate

`NON_ODDS_REALTIME_MATRIX_PASS / FIVE_TABLE_RELATIONS_742_4MB / 30D_COLD_LOGICAL_497_87MB / 30D_HISTORICAL_COLD_463_04MB / LEARNING_ALL_COLD_SMALL_AND_PROTECTED / RETENTION_UNDECIDED / NO_DELETE / FRESH_RESTORE_STILL_REQUIRED`
