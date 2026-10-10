# V4 archive remaining-consumer gate — 2026-09-15

Status: `RESEARCH_ONLY / READ_ONLY_EVIDENCE / NO_RETENTION_CUTOFF / NO_PRODUCTION_MUTATION`

This addendum narrows the archive migration backlog using evidence already produced on Draft PR #363 plus fresh default-branch and Railway Production reference scans. It does not authorize a permanent archive upload, retention cutoff, online-row deletion, schema/VACUUM action, Railway service/Cron/variable change, model/threshold change, LINE behavior change, or purchase action.

## Source-of-truth boundary

- code/runtime dependency classification is based on current `main` at `61f7d6e75629ffb549a583f00bfd5dd58c186a71`;
- Production data remains authoritative in Railway PostgreSQL;
- archive-equivalence files used by this research are ephemeral verification artifacts unless/until a permanent archive destination is separately approved;
- `30d` remains a capacity reference only and is not an approved retention cutoff;
- Draft PR changes below are **not current-main state** and cannot be used to justify deletion until they are separately reviewed/landed under the applicable approval boundary.

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

Historical readiness, Feature Lab, `compare_motor_boat_ab_pg.py`, `analyze_final_ab_features_pg.py`, and the July realtime historical export/readback tracks are already covered by earlier PR #363 evidence and remain archive-equivalence proven.

## Current-day consumers that remain online by design

These are not reasons to keep all old historical rows online:

- `run_daily_data_prepare_pg.py`: target-date scoped quality/readiness checks;
- `run_odds_window_pg.py`: active current-day acquisition/completeness and missing-odds fill path;
- safe realtime collector base-odds fallback: requested target-day/race slice only;
- legacy PRE helper while it remains active: requested day only.

They remain `KEEP ONLINE`. Archive migration must preserve their current-day working set and fail-closed completeness behavior.

## 2026-09-16 inactive-consumer retirement proof

A fresh exact-name reference scan of current `main` plus a read-only Railway Production start-command scan was used to separate historical tools that must remain operational from standalone research/diagnostic code that can be retired as an online-history consumer while retaining the source file for reproducibility.

Railway Production active/scheduled entrypoints rechecked include:

- `run_daily_data_prepare_pg.py`;
- `run_final_pg.py`;
- `run_nightly_results_pg.py`;
- `run_window_pipeline_pg.py` for morning/day/night;
- `run_daily_status_report.py`;
- `run_monthly_performance_report.py`;
- `collect_racer_course_stats_pg.py`;
- `run_learning_all_realtime_pg.py`;
- `.github/scripts/opponent_pressure_shadow_v2_compact.py`;
- `diagnose_motor2_parser_pg.py` on the service named `historical-backfill`;
- `collect_v24_motor2_forward_shadow_pg.py` on the service named `backtest-analysis`.

None invokes the three consumers below. Current main exact-name searches also find no caller/workflow entrypoint beyond each script itself and repository classification metadata.

### `backtest_v24_motor2_low_mid_grid_pg.py`

`REPOSITORY_CLASSIFICATION.md` classifies this as C / Research. It is a standalone historical grid and is not a Production or scheduled Railway entrypoint.

Retirement decision: preserve the source file and historical research meaning, but **retire the assumption that its historical odds must remain online in PostgreSQL**. After archive migration, any future rerun must first be explicitly ported to the verified archive/read-through layer or run against a separately restored research database.

Classification: `RESEARCH_SOURCE_RETAINED / ONLINE_HISTORY_CONSUMER_RETIRED / FUTURE_USE_REQUIRES_ARCHIVE_PORT_OR_RESTORE`.

### `diagnose_v24_motor2_transitions_pg.py` and `diagnose_motor2_mid_veto_pg.py`

Both are D / Maintenance-diagnostic examples in `REPOSITORY_CLASSIFICATION.md`. Exact-name scans find no current default-branch caller. The Railway Production start-command scan finds no active/scheduled service invoking either script; the current `historical-backfill` service invokes `diagnose_motor2_parser_pg.py`, not these diagnostics.

Retirement decision: retain the scripts as historical diagnostics, but retire online-history compatibility as a migration requirement. A future manual use after archival must be ported to archive/read-through or a restored research database before execution.

Classification: `DIAGNOSTIC_SOURCE_RETAINED / ONLINE_HISTORY_CONSUMER_RETIRED / NOT_ACTIVE_RUNTIME`.

## Cutover guards staged in Draft PR #363

These close the design gap in the Draft branch, but current `main` remains the Source of Truth until an approved merge/landing occurs.

### Historical month-gap repair

Current `main` `run_historical_month_gap_repair_pg.py` directly inspects `v2_odds_trifecta`, identifies incomplete historical races, and can invoke `repair_month_all_pg.py` with `REPAIR_DO_ODDS=1`. No current-main caller or active/scheduled Railway start command invokes the wrapper, but its manual semantics are dangerous after archival because intentionally archived rows could look missing online.

Draft #363 now changes the wrapper to fail closed before historical DB audit/target detection unless all required source assertions are explicit:

- default `HISTORICAL_GAP_REPAIR_ENABLE=0` blocks execution;
- `prearchive_production_full_history` is allowed only while `HISTORICAL_ARCHIVE_ACTIVE=0`;
- `restored_nonproduction_full_history` requires `HISTORICAL_GAP_REPAIR_NONPROD_ASSERT=1`;
- ambiguous source roles are rejected.

Focused CI run `34986652314` passed: compile PASS, **5/5 tests PASS**, and static ordering proved the source-role guard executes before `audit()`.

Draft classification: `GUARDED_RETIREMENT_IMPLEMENTED / CI_PASS / NOT_MERGED / NO_REPAIR_EXECUTED`.

### Bao manual online-history workflow

Current `main` `.github/workflows/bao-value-calibration-oos-readonly.yml` still exposes `workflow_dispatch` and owner issue-comment execution that loads Production historical PostgreSQL odds. The underlying `backtest_prob_calibration_pg.py` consumer already has exact archive-output equivalence evidence.

Draft #363 now retires only the **manual Production-online-history workflow wiring**:

- removes `workflow_dispatch` and `issue_comment` triggers;
- removes Railway token/database URL resolution and the Production historical report job;
- retains PR validation of the historical analysis source and archive-adapter modules;
- retains `backtest_prob_calibration_pg.py` itself for reproducibility;
- future historical reruns after archival must use the verified archive/read-through path or an explicitly restored research DB.

Draft classification: `ANALYSIS_SOURCE_RETAINED / ONLINE_HISTORY_MANUAL_WORKFLOW_RETIRED_IN_DRAFT / NOT_MERGED / NO_PRODUCTION_DB_ACCESS_ADDED`.

## Fresh Production retention reference

A read-only PR #363 run (`34983004242`) measured Railway PostgreSQL at 2026-09-15 23:38 JST with `default_transaction_read_only=on` and reconfirmed:

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
3. ensure the guarded historical-repair state and retired Bao online-history wiring are actually present in the approved cutover code state; Draft-only evidence is insufficient;
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

`ARCHIVE_EQUIVALENCE_BROADLY_PROVEN / LOW_MID_GRID_ONLINE_CONSUMER_RETIRED / MOTOR2_DIAGNOSTIC_ONLINE_CONSUMERS_RETIRED / GAP_REPAIR_GUARD_DRAFT_CI_PASS / BAO_ONLINE_HISTORY_WORKFLOW_RETIRED_IN_DRAFT / CURRENT_MAIN_STILL_PRECUTOVER / PERMANENT_ARCHIVE_NOT_CREATED / DELETE_BLOCKED / FRESH_LOGICAL_RESTORE_PROOF_PENDING / PURCHASE_FALSE`
