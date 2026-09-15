# V4 archive remaining-consumer gate — 2026-09-15

Status: `RESEARCH_ONLY / READ_ONLY_EVIDENCE / NO_RETENTION_CUTOFF / NO_PRODUCTION_MUTATION`

This addendum narrows the archive migration backlog using evidence already produced on Draft PR #363 plus a fresh default-branch reference scan on 2026-09-15 JST. It does not authorize a permanent archive upload, retention cutoff, online-row deletion, schema/VACUUM action, Railway service/Cron/variable change, model/threshold change, LINE behavior change, or purchase action.

## Source-of-truth boundary

- code/runtime dependency classification is based on current `main` at `61f7d6e75629ffb549a583f00bfd5dd58c186a71`;
- Production data remains authoritative in Railway PostgreSQL;
- archive-equivalence files used by this research are ephemeral verification artifacts unless/until a permanent archive destination is separately approved;
- `30d` remains a capacity reference only and is not an approved retention cutoff.

## Historical consumers whose archive equivalence is now proven

The latest exact-output archive matrix evidence supersedes older `equivalence pending` labels for candidate-filter and Motor2 base-candidate features. The verified output counts are:

| consumer | verified result |
|---|---|
| `backtest_prob_calibration_pg.py` | ready races 4,889; ticket rows 586,680 |
| `backtest_n02_walkforward_pg.py` | 13 bets |
| `backtest_n02_rolling_pg.py` | 13 bets |
| `backtest_n02_time_split_pg.py` | 13 bets |
| `backtest_n01_n02_diagnostics_pg.py` | N01 25 bets / N02 13 bets |
| `backtest_candidate_filter_rules_pg.py` | ready 4,889 / rule selections 586; verified stdout SHA-256 `a14d628905c392b548f0f7d9713627dc0c9ef26b5d0a830e6ca6a4b5cb985e00` |
| `backtest_v24_motor2_base_candidate_features_pg.py` | processed 4,853 / candidate rows 75; verified stdout SHA-256 `065f8e161e3cf83a77c8c3e468de1d553490c2c5024bde421eeaedce433b4f2a` |
| `backtest_v24_motor2_historical_pg.py` | processed 4,853 |

Only digests whose complete values were re-available in the current evidence record are repeated here. Other previously recorded exact-output SHA-256 values remain in the original PR #363 evidence/comments rather than being reconstructed from prefixes.

The matrix final gate was `PROB_CAL_ARCHIVE_RESULT=PASS_READ_ONLY`. The archive was removed from ephemeral runner storage before job exit. No Production rows or configuration were changed by those equivalence runs.

Historical readiness, Feature Lab, `compare_motor_boat_ab_pg.py`, `analyze_final_ab_features_pg.py`, and the July realtime historical export/readback tracks are already covered by earlier PR #363 evidence and remain archive-equivalence proven.

## Current-day consumers that remain online by design

These are not reasons to keep all old historical rows online:

- `run_daily_data_prepare_pg.py`: target-date scoped quality/readiness checks;
- `run_odds_window_pg.py`: active current-day acquisition/completeness and missing-odds fill path;
- safe realtime collector base-odds fallback: requested target-day/race slice only;
- legacy PRE helper while it remains active: requested day only.

They remain `KEEP ONLINE`. Archive migration must preserve their current-day working set and fail-closed completeness behavior.

## Residual historical/manual blockers before old online odds can be removed

### 1. `backtest_v24_motor2_low_mid_grid_pg.py`

This is a heavier manual historical research grid. Default-branch reference review found no scheduled Production entrypoint. Its archive adapter shape is compatible with the already-proven bounded odds reads, but exact-output equivalence remains intentionally deferred to avoid widening CI/timeout or weakening equality merely to force completion.

Classification: `MANUAL_RESEARCH / NOT_LIVE_RUNTIME / EQUIVALENCE_DEFERRED`.

It can be cleared either by a future bounded exact-equivalence run or by explicit retirement evidence. Its existence alone is not a reason to keep old history permanently online, but old rows must not be removed while the workflow remains expected to work only against PostgreSQL history.

### 2. `run_historical_month_gap_repair_pg.py` and related historical repair utilities

Current `main` still contains a direct `v2_odds_trifecta` historical range audit in `run_historical_month_gap_repair_pg.py`. This is maintenance/recovery logic rather than current-day scoring. Before historical odds leave the online database, this path must have one of two proofs:

1. archive-aware audit/repair semantics with explicit online/archive gap and overlap handling; or
2. obsolete/retired proof showing the maintenance path is no longer needed.

A repair tool must never silently treat archived rows as missing online data and re-ingest/reconstruct them.

Classification: `MAINTENANCE / DIRECT_HISTORICAL_SQL / ARCHIVE-AWARE-OR-RETIRE REQUIRED`.

### 3. `.github/workflows/bao-value-calibration-oos-readonly.yml`

Current `main` still has a manual `workflow_dispatch` / owner issue-comment report path that loads Production PostgreSQL and runs `backtest_prob_calibration_pg.py` for the fixed 2026-07-01..2026-08-15 range. The consumer itself has exact archive-equivalence proof, but this workflow wiring still points at online PostgreSQL historical odds.

Classification: `MANUAL_RESEARCH WORKFLOW / CONSUMER PROVEN / WIRING MIGRATION OR RETIREMENT REQUIRED`.

Before old online odds are removed, rewire this workflow to a verified archive/read-through source or explicitly retire it. Do not change its report semantics, thresholds, model coefficients, or purchase/LINE behavior as part of storage migration.

### 4. remaining Motor2 transition/mid-veto diagnostics

Any remaining historical diagnostics that indirectly assume online base odds need a final reference scan and either archive-equivalence or retirement proof. They are not current Production selector dependencies unless separately demonstrated.

Classification: `DIAGNOSTIC BACKLOG / ZERO-CONSUMER PROOF PENDING`.

## Fresh Production retention reference

A new read-only PR #363 run (`34983004242`) measured Railway PostgreSQL at 2026-09-15 23:38 JST with `default_transaction_read_only=on`. It reconfirmed, rather than assumed, the current planning reference:

- `v2_odds_trifecta`: 7,981,493 rows; logical payload 830,075,423 bytes; relation 1,844,002,816 bytes;
- 30-day reference: hot 545,940 rows / 56,777,757 logical bytes; cold 7,435,553 rows / 773,297,666 logical bytes;
- realtime relation: 536,854,528 bytes;
- `final_ab`: 1,056,020 rows; 30-day hot 498,208 / 94,924,296 bytes; cold 557,812 / 106,331,968 bytes;
- `learning_all`: 467,690 rows; 30-day hot 445,565 / 84,861,496 bytes; cold 22,125 / 4,248,000 bytes.

These are logical planning measurements except where `relation` is explicitly named. They do not authorize a cutoff and do not imply physical reclaim after DELETE.

## Permanent archive and DELETE gate remain closed

The following are still mandatory before any historical online-row removal:

1. choose and approve a permanent recoverable archive destination;
2. prove upload, immutable manifest/hash, readback, restore, and credential boundaries;
3. close the residual consumer list above by archive migration or retirement proof;
4. rerun a fresh default-branch + Railway dependency scan and require zero unclassified old-history consumers;
5. freeze exact inventory/digests for the proposed move/remove scope;
6. prove recovery from archive plus the retained online working set;
7. perform a fresh logical restore/migration rehearsal and measure the resulting PostgreSQL/volume size;
8. demonstrate enough growth/failure headroom below the Hobby per-volume limit;
9. obtain explicit approval before any Production DB deletion/schema/VACUUM or Railway migration/config action.

No `DELETE`, `VACUUM`, permanent upload, Bucket creation, Railway service/Cron/variable mutation, model/threshold/candidate change, LINE send change, or purchase action is authorized by this addendum.

## Capacity interpretation

The live Railway PostgreSQL service currently sits on a 20 GB Production volume. A Railway disk-usage metric around 4.41 GB on 2026-09-15 late JST is useful operational evidence but is **not** sufficient proof that a <=5 GB Hobby-compatible fresh volume is safe: filesystem usage, PostgreSQL logical/relation size, migration rewrite behavior, indexes/WAL/temp needs, and growth headroom are different quantities.

Therefore the Hobby gate remains:

`FRESH_LOGICAL_RESTORE_SIZE + REQUIRED_HEADROOM <= HOBBY_LIMIT`

not:

`CURRENT_DISK_METRIC < 5GB`.

## Current decision

`CANDIDATE_FILTER_ARCHIVE_EQUIVALENCE_PROVEN / MOTOR2_BASE_FEATURE_ARCHIVE_EQUIVALENCE_PROVEN / FRESH_RETENTION_REFERENCE_RECONFIRMED / LIVE_CURRENT_DAY_PATHS_KEEP_ONLINE / LOW_MID_GRID_DEFERRED_MANUAL / MONTH_GAP_REPAIR_ARCHIVE_AWARE_OR_RETIRE / BAO_WORKFLOW_REWIRE_OR_RETIRE / FINAL_ZERO_CONSUMER_SCAN_PENDING / PERMANENT_ARCHIVE_NOT_CREATED / DELETE_BLOCKED / HOBBY_FRESH_RESTORE_PROOF_PENDING / PURCHASE_FALSE`
