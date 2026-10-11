-- V5 diagnostic: metadata ONLY, exactly ONE read-only SELECT.
-- Run in Railway boat-v2-postgres > production > postgres-history-archive > Data > Query.
-- Identify whether expected v2_* tables exist in other schemas or under other names.
-- No scans of application tables, no writes, no grants, no deployments.
-- Do NOT run 1-day/7-day race SELECTs on the basis of this diagnostic.
WITH expected(table_name) AS (
  VALUES ('v2_races'),('v2_race_entries'),
         ('v2_realtime_exhibition_snapshots'),('v2_results')
),
exact_matches AS (
  SELECT e.table_name, n.nspname AS schema_name, c.relkind,
         CASE WHEN n.oid IS NULL THEN FALSE
              ELSE has_schema_privilege(n.oid, 'USAGE') END AS schema_usage,
         CASE WHEN c.oid IS NULL THEN FALSE
              ELSE has_table_privilege(c.oid, 'SELECT') END AS table_select
  FROM expected e
  LEFT JOIN pg_catalog.pg_class c ON c.relname = e.table_name
    AND c.relkind IN ('r','p','v','m','f')
  LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
),
candidate_tables AS (
  SELECT format('%I.%I', n.nspname, c.relname) AS qualified_name
  FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('r','p','v','m','f')
    AND n.nspname NOT IN ('information_schema','pg_catalog')
    AND n.nspname NOT LIKE 'pg_%'
    AND (c.relname ILIKE '%race%' OR c.relname ILIKE '%entry%'
      OR c.relname ILIKE '%result%' OR c.relname ILIKE '%exhib%'
      OR c.relname ILIKE '%history%' OR c.relname ILIKE '%archive%')
  ORDER BY n.nspname, c.relname
  LIMIT 25
),
user_relations AS (
  SELECT count(*)::integer AS total
  FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('r','p','v','m','f')
    AND n.nspname NOT IN ('information_schema','pg_catalog')
    AND n.nspname NOT LIKE 'pg_%'
)
SELECT current_database() AS connected_database,
       current_schema() AS active_schema,
       (SELECT COUNT(schema_name)::integer FROM exact_matches) AS exact_table_matches,
       COALESCE((SELECT string_agg(
           format('%I.%I (schema_usage=%s,select=%s)',
                  schema_name, table_name, schema_usage, table_select),
           ', ' ORDER BY schema_name, table_name)
           FROM exact_matches WHERE schema_name IS NOT NULL),'NONE') AS exact_table_locations,
       (SELECT total FROM user_relations) AS total_user_relations,
       COALESCE((SELECT string_agg(qualified_name, ', ' ORDER BY qualified_name)
                 FROM candidate_tables),'NONE') AS candidate_table_names,
       'METADATA_ONLY_NO_RACE_READ_AUTHORIZATION'::text AS decision
;