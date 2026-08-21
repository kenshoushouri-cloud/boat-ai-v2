# Repository Classification

Updated: 2026-08-21

This document defines how files in `boat-ai-v2` are classified before cleanup or model changes. The classification is based on the current PostgreSQL production call graph, direct imports/runpy/subprocess references, and the current repository state. File names or version numbers alone are not enough to decide whether a file is current.

## A. Production required

These files are production entrypoints or direct production dependencies. Do not move, rename, or delete them without checking Railway Start Command / Cron / Variables and the complete call graph.

### Core DB / data preparation
- `db_pg.py`
- `repair_month_all_pg.py`
- `run_daily_data_prepare_pg.py`
- `run_odds_window_pg.py`
- `collect_racer_course_stats_pg.py`

### PRE
- `run_window_pipeline_pg.py`
- `run_pre_window_pg.py`
- `v24_pre_candidate_notifier_pg.py`

### FINAL
- `run_final_pg.py`
- `v25_final_realtime_pipeline_pg.py`
- `v21_realtime_collector_pg.py`
- `run_v22_targeted_pg.py`
- `v22_realtime_decision_engine_pg.py`
- `v23_line_notifier_batch_pg.py`

### Nightly / scheduled reports
- `run_nightly_results_pg.py`
- `run_monthly_performance_report.py`
- `v27_performance_report_line.py`
- `run_daily_status_report.py`
- `v28_daily_status_report_line.py`

### Compatibility / standalone production-capable wrappers
Keep these until Railway runtime configuration is directly verified. They overlap with components already used by the FINAL pipeline but may be useful for standalone execution or older service configuration.
- `run_v21_pg.py`
- `run_v22_pg.py`
- `run_v23_pg.py`

## B. Production Shadow / production-adjacent

These do not currently change production BUY/WATCH/SKIP directly, but are invoked by production PRE/FINAL/nightly pipelines or provide their forward evaluation. They must not be treated as unused research files.

- `collect_v24_motor2_forward_shadow_pg.py`
- `collect_candidate_filter_shadow_pg.py`
- `collect_n02_windlt4_final_shadow_pg.py`
- `v22_exhibition_shadow_pg.py`
- `evaluate_candidate_filter_shadow_results_pg.py`
- `report_candidate_filter_shadow_performance_pg.py`
- `report_n02_forward_performance_pg.py`
- `evaluate_exhibition_shadow_results_pg.py`
- `report_exhibition_shadow_performance_pg.py`
- `report_n02_windlt4_variants_forward_pg.py`
- `evaluate_v24_motor2_forward_shadow_pg.py`
- `report_v24_motor2_forward_performance_pg.py`

If a future production pipeline begins calling another Shadow/evaluator/report file, that file moves from C to B immediately.

## C. Research / validation

Research files are retained because they support historical analysis, OOS, walk-forward, ablation, candidate-rule development, Motor2/N02/exhibition/previous-ST research, or feature experiments. They are not production entrypoints unless explicitly promoted.

### Default C families
Unless listed in A, B, or D, classify the following prefixes/families as C:
- `analyze_*`
- `backtest_*`
- `feature_lab_*`
- `compare_*`
- `walkforward*` / files containing `walkforward`
- historical grid / OOS / time-split / rolling analysis scripts
- model-feature analysis and calibration scripts
- `run_learning_all_realtime_pg.py`

Examples currently in C include:
- `analyze_candidate_feature_filters_phase6_oos_pg.py`
- `analyze_candidate_feature_filters_phase6_oos_v3_pg.py`
- `analyze_candidate_feature_filters_phase6_pg.py`
- `analyze_candidate_filters_pg.py`
- `analyze_candidate_grid_pg.py`
- `analyze_candidate_rules_by_venue_pg.py`
- `analyze_candidate_rules_features_pg.py`
- `analyze_candidate_walkforward_phase1_pg.py`
- `analyze_candidate_walkforward_phase2_pg.py`
- `analyze_candidate_walkforward_phase3_pg.py`
- `analyze_candidate_walkforward_phase4_pg.py`
- `analyze_exhibition_scoring_pg.py`
- `analyze_final_ab_features_pg.py`
- `analyze_final_ab_features_pg_v2.py`
- `analyze_motor_reliability_pg.py`
- `analyze_n02_final_selection_pg.py`
- `analyze_n02_phase7_features_pg.py`
- `analyze_n02_phase8_economics_pg.py`
- `analyze_n02_phase9_frequency_extension_pg.py`
- `analyze_n02_phase10_extension_filters_pg.py`
- `analyze_previous_st_conditions_pg.py`
- `analyze_previous_st_optimizer_pg.py`
- `analyze_realtime_condition_ablation_pg.py`
- `analyze_v24_motor_features_pg.py`
- `analyze_v24_motor_rank_impact_pg.py`
- `backtest_candidate_filter_rules_pg.py`
- `backtest_n01_n02_diagnostics_pg.py`
- `backtest_n02_rolling_pg.py`
- `backtest_n02_time_split_pg.py`
- `backtest_n02_walkforward_pg.py`
- `backtest_prob_calibration_pg.py`
- `backtest_v24_motor2_historical_pg.py`
- `backtest_v24_motor2_low_mid_grid_pg.py`
- `backtest_v24_motor2_base_candidate_features_pg.py`
- `evaluate_previous_st_fixed_shadow_pg.py`
- `evaluate_realtime_condition_shadow_pg.py`
- `feature_lab_no_odds_pg.py`

Research promotion rule: Historical -> OOS -> Walk-forward -> Forward Shadow -> live sample -> production decision.

## D. Maintenance / repair / diagnostics

These are operational tools, repair scripts, schema/data-quality checks, debugging helpers, probes, inspections, and one-off backfills. They may write production data, so D does not mean harmless.

### Default D families
Unless explicitly listed in A/B/C:
- `audit_*`
- `diagnose_*`
- `debug_*`
- `probe_*`
- `inspect_*`
- `repair_*` except `repair_month_all_pg.py`
- `backfill_*`
- `pg_*` check/clear/schema/diagnostic helpers
- `run_backfill_*`
- `run_gap_repair_*`
- `scripts/run_backfill_*`
- `find_*`
- `list_*`

Examples:
- `audit_k_day_all_pg.py`
- `audit_motor_boat_data_quality_pg.py`
- `audit_previous_st_month_pg.py`
- `audit_previous_st_month_pg_v2.py`
- `backfill_beforeinfo_history_pg.py`
- `backfill_historical_beforeinfo_pg.py`
- `backfill_k_date_range_pg.py`
- `diagnose_motor2_parser_pg.py`
- `diagnose_motor2_mid_veto_pg.py`
- `diagnose_v24_motor2_transitions_pg.py`
- `repair_motor2_invalid_pg.py`
- `run_gap_repair_20260701_20260815_pg.py`
- `run_backfill_from_20260601.py`
- `run_v21_debug_pg.py`
- `pg_table_check.py`
- `pg_db_size_check.py`
- `pg_backtest_ready_check.py`
- `pg_clear_line_notifications.py`
- `pg_schema_compat_v5.py`
- `debug_parse_entries_pg.py`
- `find_previous_st_writer_pg.py`
- `list_previous_st_writer_files.py`
- `inspect_feature_lab_results_pg.py`

Before running D against a historical date, use dry-run/test safeguards where supported and never allow historical replay to send LINE notifications.

## E. Legacy Supabase

Current status: no known active E files remain after the 2026-08-21 cleanup series.

Removed E groups included:
- old `app/jobs/*`
- old `data_pipeline/*`
- old `backtest/*`
- `db/client.py`
- `config/settings.py`
- old `models/*`, `betting/*`, `notifications/*`
- `main.py`, `Procfile`
- `run_nightly_results_learning.py`, `v26_nightly_results_learning.py`
- `run_odds_retention_cleanup.py`, `v29_odds_retention_cleanup.py`
- obsolete PRE wrappers `run_pre_day_pg.py`, `run_pre_night_pg.py`

If `SUPABASE_URL`, `SUPABASE_KEY`, or `/rest/v1/` appears in a newly discovered file, treat it as an E candidate until proven otherwise.

## F. Delete confirmed

Current status: no known F files remain after cleanup.

Previously removed F example:
- invisible-Unicode duplicate `diagnose_motor2_parser_pg.py⁠`, which had the same blob content as `diagnose_motor2_parser_pg.py`.

A file may enter F only when deletion is independently safe: exact duplicate, broken orphan with no runtime/reference path, or otherwise unequivocally obsolete.

## G. Repository metadata / documentation

- `.gitignore`
- `README.md`
- `REPOSITORY_CLASSIFICATION.md`
- dependency/configuration files such as `requirements.txt` if present
- `archive/*` is retained historical material and should be considered G/C unless a specific file is proven deletable.

## Conflict resolution

When a filename matches more than one family, use this priority:

1. A Production
2. B Production Shadow
3. D Maintenance if it writes/repairs/audits operational data
4. C Research
5. E Legacy
6. F Delete confirmed
7. G Metadata

Direct runtime references override prefix rules. In particular, any file invoked by `run_window_pipeline_pg.py`, `run_pre_window_pg.py`, `v25_final_realtime_pipeline_pg.py`, or `run_nightly_results_pg.py` must be treated as A or B even if its name looks like research.

## Change policy

- Never make large prediction/model changes directly on `main`.
- Use feature branch + Draft PR.
- Keep cleanup, model logic, and production promotion in separate PRs.
- For production-impact changes, state reason, files, PRE/FINAL/Shadow impact, and notification/DB risk before merge.
- Historical/replay validation: `DRY_RUN=1`, `TEST_MODE=1`, LINE disabled.
- Do not promote a high-ROI rule without OOS/walk-forward/forward/live evidence and single-hit concentration checks.
