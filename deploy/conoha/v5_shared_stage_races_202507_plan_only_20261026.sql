-- V5 stage-only preflight for safe monthly coverage: first month 2025-07.
-- EXPLAIN WITHOUT ANALYZE DOES NOT EXECUTE THE COUNT QUERY.
-- No legacy public tables, no reads of user rows, no DDL/DML, no service actions.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN READ ONLY;
SET LOCAL statement_timeout='4s';
SET LOCAL lock_timeout='500ms';
SELECT current_database() AS database,
       current_user AS db_user,
       c.relkind AS stage_relkind,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS stage_size
FROM pg_class c
WHERE c.oid = to_regclass('boat_data_stage.races');
SELECT indexrelid::regclass::text AS index_name,
       pg_get_indexdef(i.indexrelid) AS index_ddl,
       i.indisvalid AS index_valid,
       i.indisready AS index_ready
FROM pg_index i
WHERE i.indrelid = to_regclass('boat_data_stage.races')
ORDER BY i.indisprimary DESC, index_name
LIMIT 20;
-- Cost-based plan for EXACTLY ONE month, not a table count execution.
EXPLAIN (ANALYZE FALSE, COSTS TRUE, FORMAT TEXT)
SELECT count(*)
FROM boat_data_stage.races
WHERE race_date >= DATE '2025-07-01'
  AND race_date < DATE '2025-08-01';
ROLLBACK;
\echo V5_STAGE_RACES_202507_EXPLAIN_ONLY_READ_ONLY_NO_USER_ROW_SCAN_NO_MONTHLY_COUNT_BUY_OFF
