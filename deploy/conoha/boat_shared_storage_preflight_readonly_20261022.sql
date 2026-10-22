-- Version-neutral boat_data design readiness (ConoHa railway, no DB writes).
-- Staged 24 venue rows in v5_data.venues remain unused by production.
\set ON_ERROR_STOP on
\pset pager off
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '10000ms';
SET LOCAL lock_timeout = '1500ms';
SELECT 'BOAT_COMMON_SCHEMA' AS audit, n.nspname AS schema_name,
       CASE WHEN n.oid IS NULL THEN 'ABSENT_NOT_YET_CREATED'
            ELSE 'EXISTS' END AS state
FROM (VALUES ('public'), ('v5_data'), ('boat_data'), ('v5_research')) AS candidates(name)
LEFT JOIN pg_namespace n ON n.nspname=candidates.name
ORDER BY candidates.name;
SELECT 'BOAT_VENUES_LAYOUT' AS audit,
       names.fullname,
       coalesce(c.relkind::text,'ABSENT') AS relation_kind,
       CASE WHEN c.oid IS NULL THEN '-'
            ELSE pg_size_pretty(pg_total_relation_size(c.oid)) END AS total_storage,
       CASE WHEN c.oid IS NULL THEN 0 ELSE (SELECT count(*) FROM pg_index x WHERE x.indrelid=c.oid) END AS indexes
FROM (VALUES
 ('public.v2_venues'), ('v5_data.venues'), ('boat_data.venues')
) names(fullname)
LEFT JOIN pg_class c ON c.oid=to_regclass(names.fullname)
ORDER BY names.fullname;
-- This last check intentionally fails rather than falling back if pilot copy
-- does not exist or if catalog relation changed (no automatic source delete).
-- Fail-closed: a successful verdict must not print when the staged copy
-- differs from the 24-row source. Deliberately raise division_by_zero on
-- mismatch, which aborts the read-only transaction under ON_ERROR_STOP.
WITH parity AS (
 SELECT
   (SELECT count(*) FROM public.v2_venues) AS source_rows,
   (SELECT count(*) FROM v5_data.venues) AS staged_rows,
   (SELECT count(*) FROM
      (SELECT * FROM public.v2_venues
       EXCEPT ALL SELECT * FROM v5_data.venues) missing) AS missing_rows,
   (SELECT count(*) FROM
      (SELECT * FROM v5_data.venues
       EXCEPT ALL SELECT * FROM public.v2_venues) extra) AS extra_rows
)
SELECT 'BOAT_VENUES_PARITY' AS audit, source_rows, staged_rows,
       missing_rows, extra_rows,
       1 / CASE WHEN source_rows=24 AND staged_rows=24
                 AND missing_rows=0 AND extra_rows=0
                THEN 1 ELSE 0 END AS verified_gate
FROM parity;
SELECT 'BOAT_EXISTING_V5_VIEW_DEPENDENCIES' AS audit,
       view_schema, count(*) AS legacy_public_table_references
FROM information_schema.view_table_usage
WHERE view_schema IN ('v5_data','v5_research') AND table_schema='public'
GROUP BY view_schema ORDER BY view_schema;
COMMIT;
SELECT 'BOAT_SHARED_STORAGE_PREFLIGHT_READONLY_COMPLETE_NO_DB_WRITES' AS verdict;
