-- V5 bounded diagnosis: explain 2026-10-20 official K "clean six" misses.
-- READ ONLY; same official_k_file + six-lane definition as joint audit.
-- Training/fit classification only: F/L and refund information are
-- POST-RACE and MUST NEVER become a predeadline decision/BUY filter.
-- No collector changes, bulk scan, writes, or other DB.
-- usage: psql -v day=2026-10-20 -f /tmp/v5_k_six_exclusions.sql
\set ON_ERROR_STOP on
\pset pager off
\if :{?day}
\else
\set day 2026-10-20
\endif
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='15000ms';
SET LOCAL lock_timeout='1000ms';
SET LOCAL work_mem='8MB';

WITH races AS MATERIALIZED (
 SELECT race_id
 FROM boat_data.races
 WHERE race_date=:'day'::date AND race_date >= DATE '2025-07-01'
), k AS MATERIALIZED (
 SELECT h.race_id,
        count(*)::int AS k_rows,
        count(DISTINCT h.lane) FILTER (
          WHERE h.lane BETWEEN 1 AND 6)::int AS k_lanes,
        count(DISTINCT h.start_course) FILTER (
          WHERE h.start_course BETWEEN 1 AND 6)::int AS k_courses,
        count(*) FILTER (
          WHERE h.lane BETWEEN 1 AND 6
            AND h.racer_number IS NOT NULL
            AND h.start_course BETWEEN 1 AND 6
            AND h.finish_position BETWEEN 1 AND 6
            AND h.is_flying IS FALSE
            AND h.is_late IS FALSE)::int AS k_clean_rows,
        count(*) FILTER (WHERE h.is_flying IS TRUE)::int AS flying_true,
        count(*) FILTER (WHERE h.is_late IS TRUE)::int AS late_true,
        count(*) FILTER (
          WHERE h.is_flying IS NULL OR h.is_late IS NULL
        )::int AS unknown_fl,
        count(*) FILTER (
          WHERE h.start_course IS NULL
            OR h.start_course NOT BETWEEN 1 AND 6
        )::int AS invalid_course,
        count(*) FILTER (
          WHERE h.finish_position IS NULL
            OR h.finish_position NOT BETWEEN 1 AND 6
        )::int AS invalid_finish
 FROM public.v2_result_entries h
 JOIN races r USING(race_id)
 WHERE h.source='official_k_file'
 GROUP BY h.race_id
), exhibition_by_label AS MATERIALIZED (
 SELECT x.race_id,x.snapshot_label,
        (count(*)=6
         AND count(DISTINCT x.lane) FILTER (
           WHERE x.lane BETWEEN 1 AND 6
             AND x.exhibition_time_rank BETWEEN 1 AND 6)=6
         AND count(DISTINCT x.exhibition_time_rank) FILTER (
           WHERE x.lane BETWEEN 1 AND 6
             AND x.exhibition_time_rank BETWEEN 1 AND 6)=6
        ) AS complete6
 FROM boat_data.exhibition_snapshots x
 JOIN races r USING(race_id)
 GROUP BY x.race_id,x.snapshot_label
), exhibition AS MATERIALIZED (
 SELECT race_id,bool_or(complete6) AS complete6
 FROM exhibition_by_label
 GROUP BY race_id
), joined AS (
 SELECT r.race_id,
        coalesce(k.k_rows,0) AS k_rows,
        coalesce(k.k_lanes,0) AS k_lanes,
        coalesce(k.k_courses,0) AS k_courses,
        coalesce(k.k_clean_rows,0) AS k_clean_rows,
        coalesce(k.flying_true,0) AS flying_true,
        coalesce(k.late_true,0) AS late_true,
        coalesce(k.unknown_fl,0) AS unknown_fl,
        coalesce(k.invalid_course,0) AS invalid_course,
        coalesce(k.invalid_finish,0) AS invalid_finish,
        coalesce(e.complete6,FALSE) AS exhibition6
 FROM races r
 LEFT JOIN k USING(race_id)
 LEFT JOIN exhibition e USING(race_id)
)
SELECT race_id,exhibition6,k_rows,k_lanes,k_courses,k_clean_rows,
       flying_true,late_true,unknown_fl,invalid_course,invalid_finish,
       CASE
         WHEN k_rows=0 THEN 'NO_K_ROWS'
         WHEN k_rows<>6 THEN 'K_ROW_COUNT_NOT_SIX'
         WHEN k_lanes<>6 THEN 'K_LANES_NOT_SIX'
         WHEN flying_true>0 OR late_true>0 THEN 'OFFICIAL_K_F_OR_L_PRESENT'
         WHEN unknown_fl>0 THEN 'OFFICIAL_K_F_OR_L_UNKNOWN'
         WHEN k_courses<>6 THEN 'K_COURSES_NOT_SIX'
         WHEN invalid_finish>0 THEN 'K_FINISH_NOT_1_TO_6'
         WHEN k_clean_rows<>6 THEN 'OTHER_K_FIELDS_INCOMPLETE'
         ELSE 'REVIEW_K_SHAPE'
       END AS diagnostic_only_not_predecision_gate
FROM joined
WHERE NOT (k_rows=6 AND k_lanes=6 AND k_courses=6 AND k_clean_rows=6)
ORDER BY exhibition6 DESC,race_id
LIMIT 20;

COMMIT;
SELECT 'V5_K_SIX_EXCLUSIONS_READONLY_NOT_PREDECISION_NO_BUY' AS audit;
