-- V5 stage 12 empty-table bootstrap PLAN: CATALOG-ONLY, READ ONLY.
-- No CREATE/COPY/INSERT/VIEW change actually performed by this file.
-- Keep the existing verified boat_data_stage.venues untouched.
-- A proposed CREATE ... LIKE excludes defaults, identity, generated and FK;
-- review constraints/indexes/ownership/ACL and backup before separate deployment.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '

BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='12000ms';
SET LOCAL lock_timeout='1000ms';
SET LOCAL work_mem='8MB';

WITH proposed(source_name,stage_name) AS (
  VALUES
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
), state AS (
  SELECT p.*,
         to_regclass(p.source_name) AS src,
         to_regclass(p.stage_name) AS dst
  FROM proposed p
), flags AS (
  SELECT s.*,
         c.relkind AS src_kind,
         (SELECT count(*)::int FROM pg_index i
          WHERE i.indrelid=s.src AND i.indisprimary) AS pk_count,
         (SELECT count(*)::int FROM pg_attribute a
          WHERE a.attrelid=s.src AND a.attnum>0 AND NOT a.attisdropped) AS col_count,
         (SELECT count(*)::int FROM pg_attribute a
          WHERE a.attrelid=s.src AND a.attnum>0 AND NOT a.attisdropped
            AND a.attgenerated<>'') AS generated_count,
         (SELECT count(*)::int FROM pg_attrdef d
          WHERE d.adrelid=s.src) AS default_count,
         (SELECT count(*)::int FROM pg_constraint f
          WHERE f.conrelid=s.src AND f.contype='f') AS fk_count,
         (SELECT count(*)::int FROM pg_trigger t
          WHERE t.tgrelid=s.src AND NOT t.tgisinternal) AS source_user_triggers
  FROM state s
  LEFT JOIN pg_class c ON c.oid=s.src
)
SELECT source_name,
       stage_name,
       CASE
         WHEN to_regnamespace('boat_data_stage') IS NULL THEN 'STOP_STAGE_SCHEMA_MISSING'
         WHEN src IS NULL OR src_kind <> 'r' THEN 'STOP_SOURCE_NOT_REGULAR_TABLE'
         WHEN dst IS NOT NULL THEN 'STOP_TARGET_EXISTS_NEVER_OVERWRITE'
         WHEN pk_count<>1 THEN 'STOP_PK_NOT_SINGLE_CONSTRAINT'
         WHEN col_count=0 THEN 'STOP_EMPTY_SOURCE_SCHEMA'
         ELSE 'PREVIEW_ONLY_REQUIRES_INDEPENDENT_STAGE_APPROVAL'
       END AS gate,
       pk_count AS pk,
       col_count AS cols,
       generated_count AS generated,
       default_count AS source_defaults,
       fk_count AS source_fks_not_auto_copied,
       source_user_triggers AS source_user_triggers_not_auto_copied,
       CASE WHEN src IS NOT NULL
            THEN pg_size_pretty(pg_total_relation_size(src))
            ELSE '-'
       END AS source_size,
       format('CREATE TABLE %s (LIKE %s INCLUDING CONSTRAINTS INCLUDING INDEXES);',
         stage_name, source_name) AS proposed_SQL_NOT_EXECUTED
FROM flags
ORDER BY source_name;

SELECT CASE WHEN to_regclass('boat_data_stage.venues') IS NOT NULL
                 AND (SELECT relkind FROM pg_class WHERE oid=to_regclass('boat_data_stage.venues'))='r'
            THEN 'PRESERVE_EXISTING_VENUES_STAGE'
            ELSE 'STOP_VENUES_STAGE_MISSING'
       END AS venues_gate;
ROLLBACK;
SELECT 'V5_STAGE_12_BOOTSTRAP_PLAN_READ_ONLY_NO_DDL_NO_COPY' AS verdict;
