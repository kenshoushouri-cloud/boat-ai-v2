-- V5 detailed K-file result gap: last 15 COMPLETED JST race dates.
-- No writes, HTTP, K-file downloads, DDL, timer changes, or backfill.
-- Source = public.v2_result_entries; V5 snapshot = boat_data_stage.racer_results.
-- Official 3-way overall winners in v2_results do NOT prove 6-lane detail.
-- This is coverage diagnosis, not an authorization to collect/write.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL TIME ZONE 'Asia/Tokyo';
SET LOCAL statement_timeout='30000ms';
SET LOCAL lock_timeout='1200ms';
SET LOCAL work_mem='8MB';

SELECT 'DATE_WINDOW_JST' AS label,
       to_char(current_date - 15,'YYYY-MM-DD') AS from_date,
       to_char(current_date - 1,'YYYY-MM-DD') AS through_date;
SELECT 'MOST_RECENT_SOURCE_RACE_ID' AS label,
       coalesce((SELECT race_id::text FROM public.v2_result_entries
                 ORDER BY race_id DESC LIMIT 1), 'NONE') AS last_race_id;
SELECT 'MOST_RECENT_STAGE_RACE_ID' AS label,
       coalesce((SELECT race_id::text FROM boat_data_stage.racer_results
                 ORDER BY race_id DESC LIMIT 1), 'NONE') AS last_race_id;

WITH dates AS (
 SELECT generate_series(current_date - 15, current_date - 1,
                        interval '1 day')::date AS race_date
), races AS (
 SELECT race_id,race_date
 FROM public.v2_races
 WHERE race_date >= current_date - 15 AND race_date < current_date
), source_per_race AS (
 SELECT r.race_id,r.race_date,count(e.lane)::int AS source_lanes
 FROM races r
 LEFT JOIN public.v2_result_entries e ON e.race_id=r.race_id
 GROUP BY r.race_id,r.race_date
), stage_per_race AS (
 SELECT r.race_id,r.race_date,count(e.lane)::int AS stage_lanes
 FROM races r
 LEFT JOIN boat_data_stage.racer_results e ON e.race_id=r.race_id
 GROUP BY r.race_id,r.race_date
), per_day AS (
 SELECT s.race_date,
        count(*)::int AS known_races,
        coalesce(sum(s.source_lanes),0)::bigint AS source_lanes,
        coalesce(sum(t.stage_lanes),0)::bigint AS stage_lanes,
        count(*) FILTER (WHERE s.source_lanes=6)::int AS source_6_lane_races,
        count(*) FILTER (WHERE s.source_lanes=0)::int AS source_zero_races,
        count(*) FILTER (WHERE s.source_lanes BETWEEN 1 AND 5)::int AS source_partial_races,
        count(*) FILTER (WHERE s.source_lanes<>t.stage_lanes)::int AS source_stage_coverage_diff
 FROM source_per_race s JOIN stage_per_race t
   ON t.race_id=s.race_id AND t.race_date=s.race_date
 GROUP BY s.race_date
)
SELECT d.race_date,
       coalesce(p.known_races,0) AS races,
       coalesce(p.source_lanes,0) AS original_lanes,
       coalesce(p.stage_lanes,0) AS stage_lanes,
       coalesce(p.source_6_lane_races,0) AS six_lane_races,
       coalesce(p.source_zero_races,0) AS zero_lane_races,
       coalesce(p.source_partial_races,0) AS partial_races,
       coalesce(p.source_stage_coverage_diff,0) AS coverage_diff,
       CASE
         WHEN p.known_races IS NULL THEN 'NO_RACES'
         WHEN p.source_zero_races=p.known_races THEN 'SOURCE_DETAIL_ABSENT'
         WHEN p.source_stage_coverage_diff>0 THEN 'STAGE_OUT_OF_SYNC'
         WHEN p.source_zero_races>0 OR p.source_partial_races>0 THEN 'SOURCE_PARTIAL_K_COVERAGE'
         ELSE 'LANE_COUNTS_MATCH_K_COVERAGE'
       END AS status
FROM dates d LEFT JOIN per_day p ON p.race_date=d.race_date
ORDER BY d.race_date DESC;
ROLLBACK;
SELECT 'V5_K_RESULT_GAP_READONLY_NO_K_FETCH_NO_DB_WRITE_NO_CUTOVER' AS verdict;
