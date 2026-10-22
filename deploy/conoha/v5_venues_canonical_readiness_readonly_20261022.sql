-- V5 data-first staged venue verification. ONLY READS; no route changes.
-- Target already created by v5_venues_stage_pilot_20261022.py --apply.
-- This test is NOT authorization to drop public.v2_venues or enable V5.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10000ms';
SET LOCAL lock_timeout = '1500ms';

SELECT 'V5_VENUES_PHYSICAL_STATUS' AS audit,
       current_database() AS database_name,
       to_regclass('public.v2_venues') AS legacy_name,
       (SELECT relkind FROM pg_class WHERE oid=to_regclass('public.v2_venues')) AS legacy_kind,
       to_regclass('v5_data.venues') AS staged_name,
       (SELECT relkind FROM pg_class WHERE oid=to_regclass('v5_data.venues')) AS staged_kind;

WITH q AS (
 SELECT (SELECT count(*) FROM public.v2_venues) AS old_rows,
        (SELECT count(*) FROM v5_data.venues) AS staged_rows,
        (SELECT count(*) FROM (
           (SELECT * FROM public.v2_venues EXCEPT ALL SELECT * FROM v5_data.venues)
           UNION ALL
           (SELECT * FROM v5_data.venues EXCEPT ALL SELECT * FROM public.v2_venues)
        ) d) AS differences
)
SELECT 'V5_VENUES_STAGED_PARITY' AS audit,old_rows,staged_rows,differences,
       CASE WHEN old_rows=24 AND staged_rows=24 AND differences=0
            THEN 'PASS_STAGED_COPY_IDENTICAL_NOW'
            ELSE 'STOP_RECONCILE_BEFORE_ROUTE'
       END AS verdict
FROM q;

SELECT 'V5_VENUES_INDEX' AS audit,n.nspname AS schema_name,c.relname AS index_name,
       i.indisunique AS is_unique,i.indisprimary AS is_primary,
       i.indisvalid AS is_valid
FROM pg_index i
JOIN pg_class c ON c.oid=i.indexrelid
JOIN pg_class t ON t.oid=i.indrelid
JOIN pg_namespace n ON n.oid=t.relnamespace
WHERE (n.nspname,t.relname) IN (('public','v2_venues'),('v5_data','venues'))
ORDER BY schema_name,index_name;

SELECT 'V5_VENUES_DEPENDENT_VIEW' AS audit,
       n.nspname AS dependent_schema, v.relname AS dependent_view
FROM pg_depend d
JOIN pg_rewrite r ON r.oid=d.objid
JOIN pg_class v ON v.oid=r.ev_class
JOIN pg_namespace n ON n.oid=v.relnamespace
WHERE d.refobjid=to_regclass('public.v2_venues')
  AND v.relkind IN ('v','m')
ORDER BY dependent_schema,dependent_view;

COMMIT;
SELECT 'V5_VENUES_CANONICAL_READINESS_READONLY_DONE_NO_DB_WRITES' AS verdict;
