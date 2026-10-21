-- V5 physical ownership migration / STAGE 0
-- READ ONLY. No changes to tables, views, backups, collectors, or jobs.
-- Expected DB: ConoHa local PostgreSQL "railway".
-- Purpose: determine whether existing public.v2_* data can be moved
-- in-place with ALTER TABLE ... SET SCHEMA, WITHOUT a duplicate COPY.
-- DO NOT apply any schema move until application writers, views, privileges,
-- constraints and backups have been separately audited and approved.

\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15000ms';
SET LOCAL lock_timeout = '2000ms';

SELECT 'CONNECTION_AND_SIZE' AS check_name,
       current_database() AS db_name,
       pg_size_pretty(pg_database_size(current_database())) AS database_size,
       current_setting('transaction_read_only') AS read_only;

-- Maps from the approved 2026-10-21 V5 design; not a migration command.
-- Note: these *target names currently resolve to VIEWS* when installed.
WITH mapping (target_schema, target_name, source_schema, source_name, lane) AS (
 VALUES
 ('v5_data','races','public','v2_races','production'),
 ('v5_data','entries','public','v2_race_entries','production'),
 ('v5_data','results','public','v2_results','production'),
 ('v5_data','racer_results','public','v2_result_entries','production'),
 ('v5_data','exhibition_snapshots','public','v2_realtime_exhibition_snapshots','candidate'),
 ('v5_data','odds_snapshots','public','v2_realtime_odds_snapshots','candidate'),
 ('v5_data','weather_snapshots','public','v2_realtime_weather_snapshots','candidate'),
 ('v5_data','race_condition_snapshots','public','v2_realtime_race_condition_snapshots','candidate'),
 ('v5_data','racer_condition_snapshots','public','v2_realtime_racer_condition_snapshots','candidate'),
 ('v5_data','racer_course_stats_snapshots','public','v2_racer_course_stats_snapshots','candidate'),
 ('v5_data','entry_attributes_raw','public','v2_race_entries','candidate'),
 ('v5_research','motor2_legacy_shadow','public','v2_v24_motor2_forward_shadow','legacy_hold')
)
SELECT 'TABLE_VIEW_MAPPING' AS check_name,
       target_schema||'.'||target_name AS target,
       source_schema||'.'||source_name AS source,
       lane,
       COALESCE(
         CASE src.relkind
           WHEN 'r' THEN 'ordinary_table'
           WHEN 'p' THEN 'partitioned_table'
           WHEN 'f' THEN 'foreign_table'
           WHEN 'v' THEN 'view'
           WHEN 'm' THEN 'materialized_view'
           ELSE 'other_'||src.relkind::text
         END,'MISSING') AS source_kind,
       COALESCE(
         CASE dst.relkind
           WHEN 'v' THEN 'view'
           WHEN 'r' THEN 'ordinary_table'
           WHEN 'p' THEN 'partitioned_table'
           WHEN 'm' THEN 'materialized_view'
           ELSE 'other_'||dst.relkind::text
         END,'MISSING') AS target_kind,
       CASE WHEN src.oid IS NOT NULL AND src.relkind IN ('r','p','m')
            THEN pg_size_pretty(pg_total_relation_size(src.oid))
            ELSE 'n/a' END AS source_size_including_indexes,
       CASE WHEN src.oid IS NOT NULL AND src.relkind IN ('r','p','m')
            THEN src.reltuples::bigint::text ELSE 'n/a' END AS source_estimated_rows_NOT_EXACT
FROM mapping x
LEFT JOIN pg_namespace sn ON sn.nspname=x.source_schema
LEFT JOIN pg_class src ON src.relnamespace=sn.oid AND src.relname=x.source_name
LEFT JOIN pg_namespace tn ON tn.nspname=x.target_schema
LEFT JOIN pg_class dst ON dst.relnamespace=tn.oid AND dst.relname=x.target_name
ORDER BY target_schema,target_name;

-- Metadata-only dependency gates for UNIQUE physical sources.
WITH sources (source_name) AS (
 VALUES ('v2_races'),('v2_race_entries'),('v2_results'),('v2_result_entries'),
 ('v2_realtime_exhibition_snapshots'),('v2_realtime_odds_snapshots'),
 ('v2_realtime_weather_snapshots'),('v2_realtime_race_condition_snapshots'),
 ('v2_realtime_racer_condition_snapshots'),('v2_racer_course_stats_snapshots'),
 ('v2_v24_motor2_forward_shadow')
)
SELECT 'RELATION_GATES' AS check_name,
       'public.'||s.source_name AS source,
       pg_get_userbyid(c.relowner) AS owner_role,
       c.relpersistence AS persistence,
       c.relrowsecurity AS row_security,
       (SELECT count(*) FROM pg_index i WHERE i.indrelid=c.oid) AS index_count,
       (SELECT count(*) FROM pg_trigger t WHERE t.tgrelid=c.oid AND NOT t.tgisinternal) AS user_trigger_count,
       (SELECT count(*) FROM pg_constraint k WHERE k.conrelid=c.oid AND k.contype='f') AS outbound_fk_count,
       (SELECT count(*) FROM pg_constraint k WHERE k.confrelid=c.oid AND k.contype='f') AS inbound_fk_count,
       (SELECT count(*) FROM pg_inherits p WHERE p.inhparent=c.oid OR p.inhrelid=c.oid) AS inheritance_link_count,
       (SELECT count(*) FROM pg_depend d
        JOIN pg_class seq ON seq.oid=d.objid AND seq.relkind='S'
        WHERE d.refobjid=c.oid AND d.classid='pg_class'::regclass
          AND d.deptype IN ('a','i')) AS owned_sequence_count,
       (SELECT count(DISTINCT v.oid) FROM pg_depend d
        JOIN pg_rewrite rw ON rw.oid=d.objid
        JOIN pg_class v ON v.oid=rw.ev_class AND v.relkind IN ('v','m')
        WHERE d.refobjid=c.oid AND d.classid='pg_rewrite'::regclass) AS dependent_view_count
FROM sources s
LEFT JOIN pg_namespace n ON n.nspname='public'
LEFT JOIN pg_class c ON c.relnamespace=n.oid AND c.relname=s.source_name
ORDER BY source;

-- Explicit list of views that refer to source OIDs.
-- Database dependencies do not include SQL embedded in Python / shell jobs:
-- GitHub source and live systemd/cron writer paths require a SEPARATE audit.
WITH sources (source_name) AS (
 VALUES ('v2_races'),('v2_race_entries'),('v2_results'),('v2_result_entries'),
 ('v2_realtime_exhibition_snapshots'),('v2_realtime_odds_snapshots'),
 ('v2_realtime_weather_snapshots'),('v2_realtime_race_condition_snapshots'),
 ('v2_realtime_racer_condition_snapshots'),('v2_racer_course_stats_snapshots'),
 ('v2_v24_motor2_forward_shadow')
)
SELECT DISTINCT 'VIEW_DEPENDENCY' AS check_name,
       'public.'||s.source_name AS source,
       nv.nspname||'.'||v.relname AS dependent_view
FROM sources s
JOIN pg_namespace srcn ON srcn.nspname='public'
JOIN pg_class src ON src.relnamespace=srcn.oid AND src.relname=s.source_name
JOIN pg_depend d ON d.refobjid=src.oid AND d.classid='pg_rewrite'::regclass
JOIN pg_rewrite rw ON rw.oid=d.objid
JOIN pg_class v ON v.oid=rw.ev_class AND v.relkind IN ('v','m')
JOIN pg_namespace nv ON nv.oid=v.relnamespace
ORDER BY source, dependent_view;

COMMIT;
SELECT 'V5_PHYSICAL_MIGRATION_READONLY_AUDIT_COMPLETE_NO_DB_WRITES' AS verdict;
