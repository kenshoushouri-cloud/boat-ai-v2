-- V5 SHARED PHYSICAL STAGE ONLY: 2025-07 races and entries race-ID set equality.
-- Run after July entries count + 6-lane quality tests; neither proves source truth.
-- Uses indexed races.race_date and entries.race_id; no legacy or live VIEW reads.
-- No writes, no collector/timer changes, no BUY.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='500ms';
SET LOCAL work_mem='4MB';
WITH r AS MATERIALIZED (
 SELECT race_id
 FROM boat_data_stage.races
 WHERE race_date >= DATE '2025-07-01'
   AND race_date < DATE '2025-08-01'
), e AS MATERIALIZED (
 SELECT DISTINCT race_id
 FROM boat_data_stage.entries
 WHERE race_id >= '20250701_'
   AND race_id < '20250801_'
), joined AS (
 SELECT r.race_id AS race_side, e.race_id AS entry_side
 FROM r FULL OUTER JOIN e USING (race_id)
)
SELECT count(race_side) AS stage_races,
       count(entry_side) AS distinct_entry_races,
       count(*) FILTER (WHERE race_side IS NOT NULL AND entry_side IS NULL)
         AS races_without_entries,
       count(*) FILTER (WHERE race_side IS NULL AND entry_side IS NOT NULL)
         AS entry_races_without_race,
       CASE WHEN count(race_side)=5196 AND count(entry_side)=5196
                   AND count(*) FILTER (WHERE race_side IS NOT NULL AND entry_side IS NULL)=0
                   AND count(*) FILTER (WHERE race_side IS NULL AND entry_side IS NOT NULL)=0
            THEN 'RACE_ID_SET_MATCH_STAGE_ONLY_SOURCE_UNVERIFIED'
            ELSE 'HOLD_RACE_ID_SET_DIFFERENCE'
       END AS verdict
FROM joined;
ROLLBACK;
\echo V5_STAGE_RACES_ENTRIES_JULY_RACE_IDS_READ_ONLY_5S_NO_BUY
