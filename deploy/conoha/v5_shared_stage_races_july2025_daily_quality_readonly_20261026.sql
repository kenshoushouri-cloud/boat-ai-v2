-- V5 COMMON PHYSICAL STAGE ONLY. July 2025: each venue/date usually has 12 races.
-- Stage records may be copied from unverified originals: diagnostic, not proof.
-- Restrict to one month and hard stop on 5-second budget. No legacy reads/writes.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='500ms';
SET LOCAL work_mem='4MB';
WITH per_venue_day AS (
 SELECT race_date, venue_code,
        count(*) AS row_count,
        count(DISTINCT race_no) AS distinct_race_numbers,
        min(race_no) AS min_race,
        max(race_no) AS max_race,
        count(*) FILTER (
          WHERE race_id IS NULL OR race_no IS NULL
             OR venue_code IS NULL OR venue_code = ''
             OR race_id !~ '^[0-9]{8}_[0-9]{2}_[0-9]{2}$'
             OR LEFT(race_id,8) IS DISTINCT FROM to_char(race_date,'YYYYMMDD')
        ) AS bad_identifier_rows
 FROM boat_data_stage.races
 WHERE race_date >= DATE '2025-07-01' AND race_date < DATE '2025-08-01'
 GROUP BY race_date, venue_code
)
SELECT count(*) AS venue_days,
       coalesce(sum(row_count),0) AS july_rows,
       count(*) FILTER (
         WHERE row_count <> 12 OR distinct_race_numbers <> 12
            OR min_race <> 1 OR max_race <> 12
       ) AS unusual_race_count_venue_days,
       coalesce(sum(bad_identifier_rows),0) AS bad_identifier_rows,
       count(*) FILTER (WHERE race_date IS NULL OR venue_code IS NULL OR venue_code = '') AS incomplete_venue_days,
       'PROVISIONAL_COPIED_STAGE_NOT_SOURCE_VERIFIED' AS evidence_status
FROM per_venue_day;
ROLLBACK;
\echo V5_SHARED_STAGE_JULY_RACE_DAY_QA_READ_ONLY_PROVISIONAL_NO_BUY
