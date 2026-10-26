-- V5 COMMON PHYSICAL STAGE: entries index/plan only for 2025-07, no row reads.
-- This is NOT data quality verification, no join/scan executed, no production changes.
-- Fail-closed if planner chooses Seq Scan. Do not run range count until safe plan is confirmed.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='4000ms';
SET LOCAL lock_timeout='500ms';
SET LOCAL work_mem='4MB';
SELECT c.relkind AS stage_relkind,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS stage_size
FROM pg_class c
WHERE c.oid=to_regclass('boat_data_stage.entries');
SELECT indexrelid::regclass::text AS index_name,
       pg_get_indexdef(indexrelid) AS index_ddl,
       indisvalid AS index_valid,
       indisready AS index_ready
FROM pg_index
WHERE indrelid=to_regclass('boat_data_stage.entries')
ORDER BY indisprimary DESC,index_name
LIMIT 15;
-- race_id convention as seen in user data: YYYYMMDD_venue_race.
-- Text range uses lexical YYYYMMDD prefix; must verify semantic consistency separately.
EXPLAIN (ANALYZE FALSE, COSTS TRUE, FORMAT TEXT)
SELECT count(*)
FROM boat_data_stage.entries
WHERE race_id >= '20250701_'
  AND race_id < '20250801_';
EXPLAIN (ANALYZE FALSE, COSTS TRUE, FORMAT TEXT)
SELECT race_id,count(*),count(DISTINCT lane),count(DISTINCT racer_number)
FROM boat_data_stage.entries
WHERE race_id >= '20250701_'
  AND race_id < '20250801_'
GROUP BY race_id;
ROLLBACK;
\echo V5_SHARED_ENTRIES_202507_PLAN_ONLY_READ_ONLY_NO_ROW_EXEC_NO_BUY
