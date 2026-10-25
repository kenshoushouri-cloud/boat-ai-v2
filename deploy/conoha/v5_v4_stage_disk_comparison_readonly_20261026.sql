-- V4/V5 disk audit only. Exactly the 13 mapped relation pairs from
-- v5/offline_stage_batch_plan.py. NO row scans, DDL, DML, vacuum or locks.
-- pg_total_relation_size includes heap + TOAST + indexes (physical bytes).
-- Estimate only: source physical bytes != deletion-approved reclaimable bytes.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='12000ms';
SET LOCAL lock_timeout='800ms';

SELECT current_database() AS database_name,
       current_user AS role_name,
       now() AS snapshot_at,
       'READ_ONLY_PHYSICAL_ESTIMATE_NO_DELETE' AS mode;

WITH mapping(family,legacy_name,stage_name) AS (
 VALUES
 ('venues','public.v2_venues','boat_data_stage.venues'),
 ('races','public.v2_races','boat_data_stage.races'),
 ('entries','public.v2_race_entries','boat_data_stage.entries'),
 ('results','public.v2_results','boat_data_stage.results'),
 ('racer_results','public.v2_result_entries','boat_data_stage.racer_results'),
 ('trifecta_odds','public.v2_odds_trifecta','boat_data_stage.trifecta_odds'),
 ('exhibition_snapshots','public.v2_realtime_exhibition_snapshots','boat_data_stage.exhibition_snapshots'),
 ('racer_course_stats_snapshots','public.v2_racer_course_stats_snapshots','boat_data_stage.racer_course_stats_snapshots'),
 ('entry_snapshots','public.v2_realtime_entry_snapshots','boat_data_stage.entry_snapshots'),
 ('odds_snapshots','public.v2_realtime_odds_snapshots','boat_data_stage.odds_snapshots'),
 ('weather_snapshots','public.v2_realtime_weather_snapshots','boat_data_stage.weather_snapshots'),
 ('race_condition_snapshots','public.v2_realtime_race_condition_snapshots','boat_data_stage.race_condition_snapshots'),
 ('racer_condition_snapshots','public.v2_realtime_racer_condition_snapshots','boat_data_stage.racer_condition_snapshots')
), physical AS (
 SELECT m.family,
        l.relkind AS legacy_kind, t.relkind AS stage_kind,
        CASE WHEN l.relkind IN ('r','p','m')
             THEN pg_total_relation_size(l.oid) END AS legacy_bytes,
        CASE WHEN t.relkind IN ('r','p','m')
             THEN pg_total_relation_size(t.oid) END AS stage_bytes,
        CASE WHEN l.relkind IN ('r','p','m')
             THEN pg_indexes_size(l.oid) END AS legacy_index_bytes,
        CASE WHEN t.relkind IN ('r','p','m')
             THEN pg_indexes_size(t.oid) END AS stage_index_bytes
 FROM mapping m
 LEFT JOIN pg_class l ON l.oid = to_regclass(m.legacy_name)
 LEFT JOIN pg_class t ON t.oid = to_regclass(m.stage_name)
)
SELECT family,
  COALESCE(round(legacy_bytes::numeric/1048576,1)::text,'MISSING') AS v4_total_mib,
  COALESCE(round(stage_bytes::numeric/1048576,1)::text,'MISSING') AS v5_total_mib,
  COALESCE(round(legacy_index_bytes::numeric/1048576,1)::text,'MISSING') AS v4_index_mib,
  COALESCE(round(stage_index_bytes::numeric/1048576,1)::text,'MISSING') AS v5_index_mib,
  CASE WHEN legacy_kind='r' AND stage_kind='r' THEN 'BOTH_PHYSICAL'
       ELSE 'HOLD_RELATION_MISSING_OR_NONSTANDARD' END AS verdict
FROM physical
ORDER BY COALESCE(legacy_bytes,0)+COALESCE(stage_bytes,0) DESC, family;

WITH mapping(legacy_name,stage_name) AS (
 VALUES
 ('public.v2_venues','boat_data_stage.venues'),
 ('public.v2_races','boat_data_stage.races'),
 ('public.v2_race_entries','boat_data_stage.entries'),
 ('public.v2_results','boat_data_stage.results'),
 ('public.v2_result_entries','boat_data_stage.racer_results'),
 ('public.v2_odds_trifecta','boat_data_stage.trifecta_odds'),
 ('public.v2_realtime_exhibition_snapshots','boat_data_stage.exhibition_snapshots'),
 ('public.v2_racer_course_stats_snapshots','boat_data_stage.racer_course_stats_snapshots'),
 ('public.v2_realtime_entry_snapshots','boat_data_stage.entry_snapshots'),
 ('public.v2_realtime_odds_snapshots','boat_data_stage.odds_snapshots'),
 ('public.v2_realtime_weather_snapshots','boat_data_stage.weather_snapshots'),
 ('public.v2_realtime_race_condition_snapshots','boat_data_stage.race_condition_snapshots'),
 ('public.v2_realtime_racer_condition_snapshots','boat_data_stage.racer_condition_snapshots')
), sizes AS (
 SELECT l.relkind AS legacy_kind,t.relkind AS stage_kind,
        CASE WHEN l.relkind IN ('r','p','m') THEN pg_total_relation_size(l.oid) END AS legacy_bytes,
        CASE WHEN t.relkind IN ('r','p','m') THEN pg_total_relation_size(t.oid) END AS stage_bytes
 FROM mapping m
 LEFT JOIN pg_class l ON l.oid=to_regclass(m.legacy_name)
 LEFT JOIN pg_class t ON t.oid=to_regclass(m.stage_name)
)
SELECT
 count(*) AS mapped_families,
 count(*) FILTER (WHERE legacy_kind='r' AND stage_kind='r') AS both_physical,
 round(sum(COALESCE(legacy_bytes,0))::numeric/1073741824,3) AS old_source_total_gib,
 round(sum(COALESCE(stage_bytes,0))::numeric/1073741824,3) AS v5_stage_total_gib,
 round(sum(COALESCE(legacy_bytes,0)+COALESCE(stage_bytes,0))::numeric/1073741824,3)
   AS paired_storage_total_gib,
 round(sum(COALESCE(legacy_bytes,0))::numeric/1073741824,3)
   AS legacy_physical_size_gib_NOT_APPROVED_FOR_REMOVAL,
 'NO_PARITY_PROOF_NO_CUTOVER_NO_DELETE' AS verdict
FROM sizes;

-- How much else remains in public (outside the 13 known legacy sources)?
-- Estimate size of unrelated tables using catalog functions; no row scans.
SELECT n.nspname AS schema_name, c.relname AS other_table_name,
       round(pg_total_relation_size(c.oid)::numeric/1048576,1) AS size_mib,
       'OTHER_NOT_A_DUPLICATE_BY_THIS_AUDIT' AS classification
FROM pg_class c
JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public'
 AND c.relkind='r'
 AND c.relname NOT IN (
 'v2_venues','v2_races','v2_race_entries','v2_results','v2_result_entries',
 'v2_odds_trifecta','v2_realtime_exhibition_snapshots',
 'v2_racer_course_stats_snapshots','v2_realtime_entry_snapshots',
 'v2_realtime_odds_snapshots','v2_realtime_weather_snapshots',
 'v2_realtime_race_condition_snapshots','v2_realtime_racer_condition_snapshots')
ORDER BY pg_total_relation_size(c.oid) DESC, c.relname
LIMIT 10;

ROLLBACK;
SELECT 'V5_V4_DISK_AUDIT_DONE_READ_ONLY_13_PAIRS_NO_DB_WRITES_NO_DELETE_NO_CUTOVER_BUY_OFF' AS verdict;
