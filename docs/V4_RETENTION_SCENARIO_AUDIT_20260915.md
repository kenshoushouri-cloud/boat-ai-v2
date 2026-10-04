# V4 online retention scenario audit — 2026-09-15

Status: `RESEARCH_ONLY / PRODUCTION_READ_ONLY / NO_RETENTION_CHANGE / NO_DELETE / NO_VACUUM`

This note records the Production read-only retention-window measurements from GitHub Actions run `34931343677` / job `104260007481`. It does not select an online-retention cutoff and does not authorize moving or deleting any Production row.

## 1. Measurement contract

- as-of date: `2026-09-15`
- candidate online windows: `7 / 14 / 30 / 60 days`
- PostgreSQL connection forced `default_transaction_read_only=on`
- `v2_odds_trifecta` date scope uses the existing `race_id` YYYYMMDD prefix contract
- `v2_realtime_odds_snapshots` uses `race_date`
- bytes below are `sum(pg_column_size(row))` logical tuple payload bytes
- relation bytes include heap/index overhead and are shown only as context
- logical payload savings are **not** a promise of physical Railway Volume reclaim

## 2. Base trifecta odds

Current `v2_odds_trifecta`:

- rows: `7,972,734`
- logical payload: `829,164,487` bytes
- total relation: `1,841,938,432` bytes

| online window | hot rows | hot logical bytes | cold/archive-candidate rows | cold logical bytes |
|---|---:|---:|---:|---:|
| 7d | 118,764 | 12,351,453 | 7,853,970 | 816,813,034 |
| 14d | 245,587 | 25,541,045 | 7,727,147 | 803,623,442 |
| 30d | 537,181 | 55,866,821 | 7,435,553 | 773,297,666 |
| 60d | 1,116,193 | 116,084,063 | 6,856,541 | 713,080,424 |

The key live collectors are current-date/race scoped, so these old rows are not inherently required online for today's PRE/FINAL collection. They remain protected until historical consumers have verified archive read-through coverage and a permanent archive/restore contract exists.

## 3. Realtime odds

Current relation bytes: `526,999,552`.

### `final_ab`

Total: `1,046,660` rows / `199,481,040` logical bytes.

| online window | hot rows | hot logical bytes | cold rows | cold logical bytes |
|---|---:|---:|---:|---:|
| 7d | 117,825 | 22,237,200 | 928,835 | 177,243,840 |
| 14d | 244,642 | 46,545,968 | 802,018 | 152,935,072 |
| 30d | 488,848 | 93,149,072 | 557,812 | 106,331,968 |
| 60d | 884,806 | 168,637,672 | 161,854 | 30,843,368 |

### `learning_all`

Total: `458,330` rows / `87,343,400` logical bytes.

| online window | hot rows | hot logical bytes | cold rows | cold logical bytes |
|---|---:|---:|---:|---:|
| 7d | 118,425 | 22,355,280 | 339,905 | 64,988,120 |
| 14d | 191,159 | 36,313,024 | 267,171 | 51,030,376 |
| 30d | 436,205 | 83,095,400 | 22,125 | 4,248,000 |
| 60d | 458,330 | 87,343,400 | 0 | 0 |

`final_ab_debug` is only 120 rows / 23,040 logical bytes and is immaterial to capacity.

Active collection of `learning_all` remains protected. Code-scope evidence shows previous-odds lookup is same-race scoped, so old settled-date `learning_all` rows are not required for scoring a different current race; however, historical/research consumers still require preservation and read-through equivalence before any online removal.

## 4. Combined logical working-set comparison

For the two dominant odds stores (`v2_odds_trifecta` + realtime `final_ab` + `learning_all` + debug), current logical tuple payload is about `1,116,011,967` bytes.

| reference window | logical online payload | logical cold/archive payload | cold share |
|---|---:|---:|---:|
| 7d | 56,943,933 | 1,059,068,034 | ~94.9% |
| 14d | 108,400,037 | 1,007,611,930 | ~90.3% |
| 30d | 232,111,293 | 883,900,674 | ~79.2% |
| 60d | 372,065,135 | 743,946,832 | ~66.7% |

These numbers are deliberately limited to logical tuple payload in the two large odds families. They are **not** a whole-database size forecast and must not be multiplied directly into a Railway Volume estimate. A fresh logical migration is expected to reclaim dead/free/index space more effectively than in-place DELETE, but the final Hobby migration size must be measured from the candidate logical copy itself.

## 5. Interpretation

`30d` is now a useful **conservative reference scenario**, not an approved cutoff:

- it leaves far more history online than current live scoring directly requires;
- it keeps almost all currently accumulated `learning_all` evidence online;
- it would make roughly `883.9 MB` of logical odds payload eligible for archive review once consumer/restore gates are complete;
- it provides materially more headroom than 60d without immediately adopting the aggressive 7d/14d cases.

Do **not** freeze 30d solely from this capacity result. Final retention must also cover late corrections, active Forward/retraining needs, archive consumer coverage, restore drills, and a safety buffer.

## 6. Monthly service dependency refinement

Two Railway monthly services remain retirement/reconfiguration candidates:

- `historical-backfill` currently runs `diagnose_motor2_parser_pg.py`. The script reads `v2_race_entries`, fetches official pages for diagnostics, prints findings, and contains no persistent DB write path. It is operationally a diagnostic job, not a historical odds backfill.
- `backtest-analysis` currently runs `collect_v24_motor2_forward_shadow_pg.py` with a fixed old test configuration. Its write key is `(race_id,ticket,run_class,window_name,snapshot_key)` and uses `ON CONFLICT ... DO UPDATE`, so repeating the same fixed key primarily refreshes the same Shadow rows rather than creating a new monthly evidence class. The generic Motor2 performance report includes these rows in broad diagnostic input, but formal PRE scopes are limited to `morning/day/night` and FINAL to `final`; the fixed `manual/test` rows are not Production scoring inputs.

This evidence supports future service retirement review, but changing/deleting either Railway service or Cron remains a separate Production action requiring explicit approval.

## 7. Next gates

Before any online row removal or service retirement:

1. port remaining historical SQL consumers to strict archive read-through or classify them obsolete;
2. choose/create the permanent archive target only with explicit infrastructure approval;
3. permanent upload + readback + manifest/hash verification;
4. isolated restore drill with real consumer equivalence;
5. measure a fresh <=5GB logical migration candidate with the proposed online window;
6. freeze the final retention boundary and safety buffer;
7. fresh backup + exact deletion/migration inventory;
8. explicit Production approval for the exact table/label/date/service changes.

Final state:

`RETENTION_SCENARIOS_MEASURED / 30D_REFERENCE_ONLY / PERMANENT_ARCHIVE_NOT_CREATED / DELETE_BLOCKED / SERVICE_RETIREMENT_NOT_YET_APPROVED`
