-- V5/V6 shared venues move: catalog/data dependency preflight ONLY.
-- No schema/table changes, no service changes, no credential output.
-- WARNING: a clean result does not certify short-lived systemd jobs.
\set ON_ERROR_STOP on
\pset pager off
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout = '1000ms';
SET LOCAL statement_timeout = '10000ms';

-- Abort before printing PASS if any assumption has changed.
WITH gate AS (
 SELECT current_database() = 'railway' AS correct_database,
        to_regnamespace('boat_data') IS NOT NULL AS schema_exists,
        (SELECT relkind = 'r' FROM pg_class
         WHERE oid = to_regclass('v5_data.venues')) AS staged_physical,
        to_regclass('boat_data.venues') IS NULL AS destination_absent,
        (SELECT count(*) FROM public.v2_venues) AS original_rows,
        (SELECT count(*) FROM v5_data.venues) AS staged_rows,
        (SELECT count(*) FROM (
          SELECT * FROM public.v2_venues
          EXCEPT ALL SELECT * FROM v5_data.venues
        ) diff) AS missing_rows,
        (SELECT count(*) FROM (
          SELECT * FROM v5_data.venues
          EXCEPT ALL SELECT * FROM public.v2_venues
        ) diff) AS extra_rows
)
SELECT 'VENUES_MOVE_READONLY_GATE' AS audit, correct_database,
       schema_exists, staged_physical, destination_absent,
       original_rows, staged_rows, missing_rows, extra_rows,
       1 / CASE WHEN correct_database AND schema_exists
                AND staged_physical IS TRUE AND destination_absent
                AND original_rows=24 AND staged_rows=24
                AND missing_rows=0 AND extra_rows=0
                THEN 1 ELSE 0 END AS verified_gate
FROM gate;

SELECT 'VENUES_STAGE_DEPENDENT_VIEWS' AS audit,
       nv.nspname AS view_schema, v.relname AS view_name
FROM pg_depend d
JOIN pg_rewrite rw ON rw.oid = d.objid
JOIN pg_class v ON v.oid = rw.ev_class
JOIN pg_namespace nv ON nv.oid = v.relnamespace
WHERE d.classid = 'pg_rewrite'::regclass
  AND d.refobjid = to_regclass('v5_data.venues')
  AND v.relkind IN ('v','m')
ORDER BY nv.nspname,v.relname;

SELECT 'VENUES_STAGE_FK_DEPENDENCIES' AS audit,
       conname, conrelid::regclass::text AS on_table,
       confrelid::regclass::text AS referenced_table
FROM pg_constraint
WHERE contype='f' AND (conrelid=to_regclass('v5_data.venues')
                       OR confrelid=to_regclass('v5_data.venues'))
ORDER BY conname;

SELECT 'VENUES_STAGE_USER_TRIGGERS' AS audit,
       tgname, tgenabled
FROM pg_trigger
WHERE tgrelid=to_regclass('v5_data.venues')
  AND NOT tgisinternal
ORDER BY tgname;

SELECT 'VENUES_STAGE_LAYOUT' AS audit,
       pg_get_userbyid(c.relowner) AS owner,
       c.relrowsecurity AS row_security_enabled,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS table_total_size,
       (SELECT count(*) FROM pg_index i WHERE i.indrelid=c.oid) AS index_count,
       (SELECT count(*) FROM pg_policy p WHERE p.polrelid=c.oid) AS policy_count
FROM pg_class c
WHERE c.oid=to_regclass('v5_data.venues');

SELECT 'VENUES_STAGE_INDEX' AS audit, n.nspname AS index_schema,
       ci.relname AS index_name, i.indisprimary AS is_primary,
       i.indisunique AS is_unique
FROM pg_index i
JOIN pg_class ci ON ci.oid=i.indexrelid
JOIN pg_namespace n ON n.oid=ci.relnamespace
WHERE i.indrelid=to_regclass('v5_data.venues')
ORDER BY index_name;

COMMIT;
SELECT 'VENUES_MOVE_DEPENDENCIES_READONLY_COMPLETE_NO_DB_WRITES' AS verdict;
