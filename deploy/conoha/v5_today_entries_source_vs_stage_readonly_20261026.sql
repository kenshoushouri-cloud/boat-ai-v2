-- 2026-10-26 V5 stage missing entries: diagnostic of the active collection SOURCE versus copied STAGE.
-- Source is public.v2_race_entries exposed by boat_data.entries VIEW; limited to today's race_id.
-- This test may reveal source/stage LAG, but DOES NOT prove entries existed before a race's cutoff.
-- Read-only 5s; stop if timeout. No sync, no collectors, no inference, no BUY.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='500ms';
SET LOCAL work_mem='4MB';
WITH stage_missing AS MATERIALIZED (
 SELECT r.race_id
 FROM boat_data_stage.races r
 WHERE r.race_date=DATE '2026-10-26'
   AND NOT EXISTS (
     SELECT 1 FROM boat_data_stage.entries e WHERE e.race_id=r.race_id
   )
), source_today AS MATERIALIZED (
 SELECT e.race_id,e.lane,e.racer_number
 FROM public.v2_race_entries e
 WHERE e.race_id >= '20261026_'
   AND e.race_id < '20261027_'
), matched AS (
 SELECT m.race_id,
        count(s.race_id) AS source_rows,
        count(DISTINCT s.lane) AS source_lanes,
        count(DISTINCT s.racer_number) AS source_racers
 FROM stage_missing m
 LEFT JOIN source_today s ON m.race_id=s.race_id
 GROUP BY m.race_id
)
SELECT count(*) AS stage_missing_races,
       count(*) FILTER (WHERE source_lanes=6 AND source_racers=6
                             AND source_rows=6) AS already_complete_in_live_source,
       count(*) FILTER (WHERE source_rows=0) AS also_absent_in_live_source,
       count(*) FILTER (WHERE source_rows>0 AND
                      (source_rows<>6 OR source_lanes<>6 OR source_racers<>6))
                      AS incomplete_in_live_source,
       coalesce(sum(source_rows),0) AS live_source_rows_for_stage_missing,
       CASE
         WHEN count(*)=0 THEN 'STAGE_ALREADY_CAUGHT_UP'
         WHEN count(*) FILTER (WHERE source_lanes=6 AND source_racers=6 AND source_rows=6)
              =count(*) THEN 'SOURCE_HAS_ALL_ROWS_STAGE_SYNC_LAG_CURRENT_ONLY'
         ELSE 'SOURCE_AND_STAGE_MIXED_GAPS_INVESTIGATE_COLLECTION'
       END AS verdict
FROM matched;
ROLLBACK;
\echo V5_TODAY_SOURCE_VS_STAGE_DIAGNOSTIC_READ_ONLY_CURRENT_STATE_NOT_PREDEADLINE_PROOF_NO_BUY
