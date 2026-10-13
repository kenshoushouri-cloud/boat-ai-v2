-- V3/V5 migration-preservation first-pass inventory (2026-10-13)
-- Execute ONE copy of this identical query in Railway Data > Query for each:
--   postgres-hobby-fullhistory-candidate-v3 (sleeping; a query may wake it)
--   postgres-hobby-fullhistory-candidate-v4 (V5 research DB)
-- NO writes, dumps, restarts, schema scans or full table COUNT(*).
-- pg_class.reltuples is an APPROXIMATE planner estimate, not authoritative.
-- Same table names/estimates DO NOT prove identical data or no unique records.
-- Do NOT delete/archive V3 on the strength of this inventory alone.
WITH user_tables AS (
  SELECT c.oid, n.nspname, c.relname, c.reltuples
  FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('r', 'p')
    AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    AND n.nspname NOT LIKE 'pg_toast%'
)
SELECT current_database() AS database_name,
       current_setting('server_version') AS postgres_version,
       (SELECT count(*) FROM user_tables) AS user_table_count,
       nspname AS schema_name,
       relname AS table_name,
       CASE WHEN reltuples < 0 THEN NULL ELSE reltuples::bigint END AS approximate_rows,
       pg_total_relation_size(oid) AS table_and_indexes_bytes
FROM user_tables
ORDER BY table_and_indexes_bytes DESC, schema_name, table_name
LIMIT 60;
