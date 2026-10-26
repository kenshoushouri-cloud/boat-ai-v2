-- V5 SHARED stage ONLY: July 2025 per-race six-lane structural audit.
-- 2025-07 stage races count=5196 and stage entries count=31176 observed in user screenshots.
-- Stage values have NOT been externally verified as true/original pre-deadline.
-- Read-only index-bounded workload: no legacy/source VIEW joins, no DDL/DML.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='500ms';
SET LOCAL work_mem='4MB';
WITH per_race AS MATERIALIZED (
  SELECT race_id,
         count(*) AS rows_per_race,
         count(DISTINCT lane) AS distinct_lanes,
         min(lane) AS min_lane,
         max(lane) AS max_lane,
         count(DISTINCT racer_number) AS distinct_racers,
         count(*) FILTER (WHERE lane IS NULL OR lane NOT BETWEEN 1 AND 6
                            OR racer_number IS NULL
                            OR racer_number NOT BETWEEN 1 AND 9999) AS invalid_rows
  FROM boat_data_stage.entries
  WHERE race_id >= '20250701_'
    AND race_id < '20250801_'
  GROUP BY race_id
)
SELECT count(*) AS entry_races,
       coalesce(sum(rows_per_race),0) AS entry_rows,
       count(*) FILTER (WHERE rows_per_race <> 6
                         OR distinct_lanes <> 6
                         OR min_lane <> 1 OR max_lane <> 6) AS six_lane_holds,
       count(*) FILTER (WHERE distinct_racers <> 6) AS distinct_racer_holds,
       coalesce(sum(invalid_rows),0) AS invalid_identity_rows,
       CASE WHEN count(*)=5196 AND coalesce(sum(rows_per_race),0)=31176
                 AND count(*) FILTER (WHERE rows_per_race <> 6
                          OR distinct_lanes <> 6
                          OR min_lane <> 1 OR max_lane <> 6
                          OR distinct_racers <> 6 OR invalid_rows <> 0)=0
            THEN 'STRUCTURE_ONLY_OK_RACE_SET_NOT_COMPARED_SOURCE_UNVERIFIED'
            ELSE 'HOLD_STAGE_ENTRY_STRUCTURE'
       END AS verdict
FROM per_race;
ROLLBACK;
\echo V5_STAGE_ENTRIES_202507_SIX_LANES_READ_ONLY_5S_NO_SOURCE_JOIN_NO_BUY
