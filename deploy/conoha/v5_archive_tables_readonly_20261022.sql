-- V5 historical-source audit: catalog only, no data scan or writes.
-- Run against local PostgreSQL database boat_history_archive (NOT railway).
-- Existence/size do NOT certify historical coverage from 2025-07 onward.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10000ms';
SET LOCAL lock_timeout = '1000ms';
SELECT 'V5_ARCHIVE_OVERVIEW' AS audit,
       current_database() AS db_name,
       pg_size_pretty(pg_database_size(current_database())) AS db_size,
       COUNT(*) FILTER (WHERE c.relkind IN ('r','p')) AS table_count,
       COUNT(*) FILTER (WHERE c.relkind='v') AS view_count
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname <> 'information_schema' AND n.nspname NOT LIKE 'pg_%';
SELECT 'V5_ARCHIVE_LARGEST_RELATIONS' AS audit,
       n.nspname AS schema_name, c.relname AS relation_name,
       c.relkind AS relation_kind,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
       CASE WHEN c.reltuples < 0 THEN 'UNKNOWN'
            ELSE c.reltuples::bigint::text END AS estimated_rows_not_exact
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname <> 'information_schema' AND n.nspname NOT LIKE 'pg_%'
  AND c.relkind IN ('r','p','m')
ORDER BY pg_total_relation_size(c.oid) DESC, n.nspname, c.relname LIMIT 20;
COMMIT;
SELECT 'V5_ARCHIVE_TABLE_CATALOG_READONLY_DONE_NO_DB_WRITES' AS verdict;
