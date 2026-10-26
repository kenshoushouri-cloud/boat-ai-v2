-- V5 SHARED PHYSICAL DATA ONLY. 2025-07 through 2026-10 monthly race/day checks.
-- Preview / provisional source data: not a truth guarantee, and no BUY eligibility.
-- Scans only small (~19 MB) boat_data_stage.races, once; no legacy tables/joins.
-- If 5 seconds is exceeded, STOP, do not extend/retry during collector hours.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='500ms';
SET LOCAL work_mem='4MB';
WITH per_venue_day AS MATERIALIZED (
 SELECT date_trunc('month', race_date)::date AS month_start,
        race_date, venue_code,
        count(*) AS rows_per_day,
        count(DISTINCT race_no) AS unique_race_numbers,
        min(race_no) AS first_race,
        max(race_no) AS last_race,
        count(*) FILTER (WHERE race_id IS NULL OR race_no IS NULL
          OR venue_code IS NULL OR venue_code = ''
          OR race_id !~ '^[0-9]{8}_[0-9]{2}_[0-9]{2}$'
          OR left(race_id,8) IS DISTINCT FROM to_char(race_date,'YYYYMMDD')
          OR right(race_id,2) IS DISTINCT FROM lpad(race_no::text,2,'0')
        ) AS invalid_id_rows
 FROM boat_data_stage.races
 WHERE race_date >= DATE '2025-07-01'
   AND race_date < DATE '2026-11-01'
 GROUP BY date_trunc('month', race_date)::date, race_date, venue_code
), monthly AS (
 SELECT month_start, count(*) AS venue_days, sum(rows_per_day) AS races,
        count(*) FILTER (
          WHERE rows_per_day<>12 OR unique_race_numbers<>12
             OR first_race<>1 OR last_race<>12
        ) AS anomalous_venue_days,
        sum(invalid_id_rows) AS invalid_id_rows
 FROM per_venue_day
 GROUP BY month_start
), months AS (
 SELECT (DATE '2025-07-01' + (n * INTERVAL '1 month'))::date AS month_start
 FROM generate_series(0,15) AS g(n)
)
SELECT to_char(m.month_start,'YYYY-MM') AS month,
       coalesce(q.venue_days,0) AS venue_days,
       coalesce(q.races,0) AS race_rows,
       coalesce(q.anomalous_venue_days,0) AS anomalous_venue_days,
       coalesce(q.invalid_id_rows,0) AS invalid_id_rows,
       CASE
         WHEN q.month_start IS NULL THEN 'HOLD_NO_STAGE_MONTH'
         WHEN q.anomalous_venue_days > 0 OR q.invalid_id_rows > 0 THEN 'HOLD_STAGE_INTERNAL_MISMATCH'
         WHEN m.month_start = DATE '2026-10-01' THEN 'INTERNAL_OK_CURRENT_MONTH_PARTIAL_SOURCE_UNVERIFIED'
         ELSE 'INTERNAL_OK_SOURCE_UNVERIFIED'
       END AS verdict
FROM months m
LEFT JOIN monthly q USING(month_start)
ORDER BY m.month_start;
ROLLBACK;
\echo V5_SHARED_STAGE_RACES_16MONTH_QA_READ_ONLY_NO_WRITES_NO_BUY_NO_FULL_13FAMILY_SCAN
