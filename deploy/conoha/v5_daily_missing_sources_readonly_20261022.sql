-- V5 migration stage 1: verify existing daily-writer source tables.
-- READ-ONLY ONLY. No DDL, no COPY, no row changes, no service changes.
-- This check does not validate the runtime writer's permissions or all dependencies.
\set ON_ERROR_STOP on
\pset pager off

BEGIN READ ONLY;
SET LOCAL statement_timeout = '15000ms';
SET LOCAL lock_timeout = '2000ms';

SELECT 'DAILY_SOURCE_CONTEXT' AS check_name,
       current_database() AS database_name,
       current_setting('transaction_read_only') AS transaction_read_only;

WITH daily_targets (name, v5_name, reason) AS (
 VALUES
 ('v2_venues', 'venues', 'daily_venue_master'),
 ('v2_races', 'races', 'daily_race'),
 ('v2_race_entries', 'entries', 'daily_entry'),
 ('v2_results', 'results', 'daily_result'),
 ('v2_odds_trifecta', 'trifecta_odds', 'daily_odds'),
 ('v2_result_entries', 'racer_results', 'separate_k_six_lane_result')
)
SELECT 'DAILY_SOURCE_TABLE' AS check_name,
       'public.' || d.name AS source,
       'v5_data.' || d.v5_name AS v5_candidate,
       d.reason,
       COALESCE(
         CASE source_rel.relkind
           WHEN 'r' THEN 'TABLE'
           WHEN 'p' THEN 'PARTITIONED_TABLE'
           WHEN 'v' THEN 'VIEW'
           WHEN 'm' THEN 'MATERIALIZED_VIEW'
           ELSE 'OTHER_' || source_rel.relkind::text
         END, 'MISSING') AS source_kind,
       COALESCE(
         CASE dest_rel.relkind
           WHEN 'r' THEN 'TABLE'
           WHEN 'p' THEN 'PARTITIONED_TABLE'
           WHEN 'v' THEN 'VIEW'
           WHEN 'm' THEN 'MATERIALIZED_VIEW'
           ELSE 'OTHER_' || dest_rel.relkind::text
         END, 'MISSING') AS v5_target_kind,
       CASE WHEN source_rel.relkind IN ('r','p','m')
            THEN pg_size_pretty(pg_total_relation_size(source_rel.oid))
            ELSE 'n/a' END AS source_total_size,
       CASE WHEN source_rel.relkind IN ('r','p','m')
            THEN source_rel.reltuples::bigint::text
            ELSE 'n/a' END AS estimated_rows_not_exact
FROM daily_targets d
LEFT JOIN pg_namespace source_ns ON source_ns.nspname='public'
LEFT JOIN pg_class source_rel ON source_rel.relnamespace=source_ns.oid
                             AND source_rel.relname=d.name
LEFT JOIN pg_namespace dest_ns ON dest_ns.nspname='v5_data'
LEFT JOIN pg_class dest_rel ON dest_rel.relnamespace=dest_ns.oid
                           AND dest_rel.relname=d.v5_name
ORDER BY d.name;

COMMIT;
SELECT 'V5_DAILY_MISSING_SOURCES_READONLY_COMPLETE_NO_DB_WRITES' AS verdict;
