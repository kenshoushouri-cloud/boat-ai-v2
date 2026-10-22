-- V5 prediction/backtest migration scope completeness: PostgreSQL catalog-only audit.
-- Existing copy-first preflight covers only 12 source tables; THIS extends
-- inventory to direct features, historical course statistics, research-only
-- motor shadow and missing inference-evidence destinations.
-- No SELECT against user data, no DDL/DML, no HTTP or timer operations.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10000ms';
SET LOCAL lock_timeout = '1000ms';
WITH inputs(kind,source,desired_v5,policy) AS (
 VALUES
 ('core','public.v2_venues','v5_data.venues','MIGRATE'),
 ('core','public.v2_races','v5_data.raw_races','MIGRATE'),
 ('core','public.v2_race_entries','v5_data.raw_entries','MIGRATE_WITH_FEATURE_COLUMNS'),
 ('core','public.v2_results','v5_data.raw_results','MIGRATE_POSTRACE_LABEL_ONLY'),
 ('core','public.v2_result_entries','v5_data.raw_racer_results','MIGRATE_POSTRACE_LABEL_ONLY'),
 ('core','public.v2_odds_trifecta','v5_data.trifecta_odds','MIGRATE_TIMING_AUDIT'),
 ('realtime','public.v2_realtime_entry_snapshots','v5_data.raw_entry_snapshots','MIGRATE_CAPTURE_EVIDENCE'),
 ('realtime','public.v2_realtime_exhibition_snapshots','v5_data.raw_exhibition_snapshots','MIGRATE_CAPTURE_EVIDENCE'),
 ('realtime','public.v2_realtime_odds_snapshots','v5_data.raw_odds_snapshots','MIGRATE_CAPTURE_EVIDENCE'),
 ('realtime','public.v2_realtime_weather_snapshots','v5_data.raw_weather_snapshots','MIGRATE_CAPTURE_EVIDENCE'),
 ('realtime','public.v2_realtime_race_condition_snapshots','v5_data.raw_race_condition_snapshots','MIGRATE_CAPTURE_EVIDENCE'),
 ('realtime','public.v2_realtime_racer_condition_snapshots','v5_data.raw_racer_condition_snapshots','MIGRATE_CAPTURE_EVIDENCE'),
 ('additional','public.v2_racer_course_stats_snapshots','v5_data.raw_racer_course_stats_snapshots','REQUIRES_COPY_PLAN'),
 ('research','public.v2_v24_motor2_forward_shadow','v5_research.raw_motor2_legacy_shadow','ARCHIVE_ONLY_NOT_LIVE_PREDICTION')
), resolved AS (
 SELECT *,to_regclass(source) AS src_oid,to_regclass(desired_v5) AS dst_oid FROM inputs
)
SELECT 'V5_PREDICTION_SOURCE_COVERAGE' AS audit,kind,source,
       COALESCE(s.relkind::text,'MISSING') AS source_kind,
       CASE WHEN src_oid IS NULL THEN 'N/A' ELSE pg_size_pretty(pg_total_relation_size(src_oid)) END AS approx_storage_including_indexes,
       desired_v5, COALESCE(t.relkind::text,'ABSENT') AS v5_physical_kind,policy
FROM resolved
LEFT JOIN pg_class s ON s.oid=src_oid
LEFT JOIN pg_class t ON t.oid=dst_oid
ORDER BY kind,source;
WITH wanted(col,reason) AS (
 VALUES
 ('recent_form','RECENT_FORM_PAST5_ASOF_NO_PREDECISION_PROOF_FROM_DATE_ONLY'),
 ('racer_number','PLAYER_ID'),
 ('racer_class','PLAYER_RANK'),
 ('motor_no','MOTOR_GENERATION_JOIN_KEY'),
 ('motor_place2_rate','MOTOR_SAMPLE_MATURITY_REQUIRED'),
 ('motor_place3_rate','MOTOR_SAMPLE_MATURITY_REQUIRED'),
 ('boat_no','BOAT_JOIN_KEY'),
 ('boat_place2_rate','BOAT_SAMPLE_MATURITY_REQUIRED'),
 ('boat_place3_rate','BOAT_SAMPLE_MATURITY_REQUIRED'),
 ('local_place2_rate','VENUE_AFFINITY'),
 ('local_place3_rate','VENUE_AFFINITY')
)
SELECT 'V5_EMBEDDED_ENTRY_FEATURE' AS audit,w.col,
       CASE WHEN a.attname IS NULL THEN 'MISSING' ELSE format_type(a.atttypid,a.atttypmod) END AS source_type,
       w.reason
FROM wanted w LEFT JOIN pg_attribute a ON a.attrelid=to_regclass('public.v2_race_entries')
   AND a.attname=w.col AND a.attnum>0 AND NOT a.attisdropped
ORDER BY w.col;
SELECT 'V5_ARCHIVE_DATABASE_PRESENT' AS audit,datname
FROM pg_database WHERE datname ILIKE '%histor%' OR datname ILIKE '%archiv%';
COMMIT;
SELECT 'V5_PREDICTION_COVERAGE_CATALOG_READONLY_DONE_NO_DB_WRITES' AS verdict;
