-- Current-day original V5 collector entries: field-null quality diagnostics.
-- Avoids any official HTTP, DML, service changes or collection restarts.
-- The morning collector may still be running; numbers are as-of snapshot.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL TIME ZONE 'Asia/Tokyo';
SET LOCAL statement_timeout='12000ms';
SET LOCAL lock_timeout='800ms';
SET LOCAL work_mem='4MB';
WITH todays AS MATERIALIZED (
  SELECT e.race_id, r.venue_code, e.lane, e.racer_number,
    e.avg_st, e.national_win_rate, e.local_win_rate, e.motor_no, e.boat_no
  FROM boat_data.entries e
  JOIN boat_data.races r USING (race_id)
  WHERE r.race_date = CURRENT_DATE
)
SELECT venue_code,
 count(DISTINCT race_id) AS race_count,
 count(*) AS entry_lanes,
 count(*) FILTER (WHERE racer_number IS NULL) AS missing_racer_id,
 count(*) FILTER (WHERE avg_st IS NULL) AS missing_avg_st,
 count(*) FILTER (WHERE national_win_rate IS NULL) AS missing_national_win_rate,
 count(*) FILTER (WHERE local_win_rate IS NULL) AS missing_local_win_rate,
 count(*) FILTER (WHERE motor_no IS NULL) AS missing_motor,
 count(*) FILTER (WHERE boat_no IS NULL) AS missing_boat,
 count(*) FILTER (
   WHERE racer_number IS NOT NULL AND avg_st IS NULL
     AND national_win_rate IS NULL AND local_win_rate IS NULL
     AND motor_no IS NULL AND boat_no IS NULL
 ) AS probable_stats_parse_gaps
FROM todays
GROUP BY venue_code ORDER BY venue_code;

SELECT 'V5_MORNING_ENTRY_STATS_AUDIT_AS_OF_READONLY_NO_REPAIR_NO_CUTOVER' AS verdict;
ROLLBACK;
