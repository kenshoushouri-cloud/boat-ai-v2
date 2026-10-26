-- Provisional 2025-07 to 2026-10 staged V5 race monthly row counts.
-- ONLY boat_data_stage.races; no legacy source/VIEW scans, joins, DML or DDL.
-- 2026-10-26: index-only access candidate checked by EXPLAIN (no ANALYZE);
-- actual results remain provisional until scheduled stage11 delta is verified.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='500ms';
SET LOCAL work_mem='4MB';
WITH months AS (
 SELECT (DATE '2025-07-01' + (n * INTERVAL '1 month'))::date AS first_day
 FROM generate_series(0,15) AS g(n)
)
SELECT to_char(m.first_day, 'YYYY-MM') AS race_month,
       (SELECT count(*)
          FROM boat_data_stage.races r
         WHERE r.race_date >= m.first_day
           AND r.race_date < (m.first_day + INTERVAL '1 month')::date) AS stage_rows,
       CASE
         WHEN m.first_day = date_trunc('month', now() AT TIME ZONE 'Asia/Tokyo')::date
         THEN 'CURRENT_MONTH_PARTIAL'
         ELSE 'STAGE_COUNT_NOT_YET_PROVEN_COMPLETE'
       END AS evidence_status
FROM months m
ORDER BY m.first_day;
ROLLBACK;
\echo V5_STAGE_RACES_16_MONTHS_READ_ONLY_PROVISIONAL_NO_SCHEMA_CHANGE_NO_BUY
