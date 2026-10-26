-- V5 shared physical stage ONLY: October 2026 races with NO corresponding entry race_id.
-- Diagnostic of 144 races reported 2026-10-26 20:44 JST. Do not assume source truth.
-- Narrow stage races by indexed race_date; probe stage entries via race_id btree index.
-- Read only; DO NOT backfill, merge, change timers, or enable BUY.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='500ms';
SET LOCAL work_mem='4MB';
WITH missing AS MATERIALIZED (
 SELECT r.race_date, r.venue_code, r.race_no, r.race_id
 FROM boat_data_stage.races r
 WHERE r.race_date >= DATE '2026-10-01'
   AND r.race_date < DATE '2026-11-01'
   AND NOT EXISTS (
     SELECT 1
     FROM boat_data_stage.entries e
     WHERE e.race_id = r.race_id
   )
)
SELECT to_char(race_date,'YYYY-MM-DD') AS race_date,
       venue_code,
       count(*) AS missing_races,
       min(race_no) AS first_race,
       max(race_no) AS last_race,
       string_agg(lpad(race_no::text,2,'0'),',' ORDER BY race_no) AS missing_race_numbers,
       CASE WHEN race_date > (now() AT TIME ZONE 'Asia/Tokyo')::date
            THEN 'FUTURE_RACE_STAGE_NOT_YET_VERIFIED'
            WHEN race_date = (now() AT TIME ZONE 'Asia/Tokyo')::date
            THEN 'TODAY_STAGE_LAG_POSSIBLE'
            ELSE 'PAST_STAGE_GAP_REVIEW_AFTER_DELTA'
       END AS timing_hint
FROM missing
GROUP BY race_date, venue_code
ORDER BY race_date,venue_code;
ROLLBACK;
\echo V5_STAGE_OCT2026_MISSING_ENTRY_IDS_BY_DAY_VENUE_READ_ONLY_5S_NO_WRITES_NO_BUY
