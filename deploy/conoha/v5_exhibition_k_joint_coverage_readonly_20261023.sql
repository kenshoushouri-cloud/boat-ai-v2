-- V5 single-day joint training-source SHAPE audit (READ ONLY).
-- 2026-10-20: roster 144, clean K course 132, exhibition 6 per label 29
-- observed independently. Check the INTERSECTION; do not assume 29 qualify.
-- These are retrospective source-shape checks ONLY, not historical
-- first-availability/official-six-active/incident/refund/profit evidence.
-- No DB writes, HTTP, migrations, model fit, or BUY.
-- Usage: psql -v day=2026-10-20 -f /tmp/v5_exhibition_k_joint.sql
\set ON_ERROR_STOP on
\pset pager off
\if :{?day}
\else
\set day 2026-10-20
\endif
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '15000ms';
SET LOCAL lock_timeout = '1000ms';
SET LOCAL work_mem = '8MB';

WITH races AS MATERIALIZED (
 SELECT race_id, deadline_at
 FROM boat_data.races
 WHERE race_date = :'day'::date
   AND race_date >= DATE '2025-07-01'
), roster AS MATERIALIZED (
 SELECT e.race_id,
        (count(*)=6
         AND count(DISTINCT e.lane) FILTER (WHERE e.lane BETWEEN 1 AND 6)=6
         AND count(DISTINCT e.racer_number) FILTER (
               WHERE e.racer_number IS NOT NULL)=6
         AND count(*) FILTER (
               WHERE e.lane BETWEEN 1 AND 6
                 AND e.racer_number IS NOT NULL
                 AND e.racer_class IS NOT NULL
                 AND trim(e.racer_class::text)<>'')=6) AS full6
 FROM boat_data.entries e
 JOIN races r USING (race_id)
 GROUP BY e.race_id
), k AS MATERIALIZED (
 SELECT h.race_id,
        (count(*)=6
         AND count(DISTINCT h.lane) FILTER (
               WHERE h.lane BETWEEN 1 AND 6)=6
         AND count(DISTINCT h.start_course) FILTER (
               WHERE h.start_course BETWEEN 1 AND 6)=6
         AND count(*) FILTER (
               WHERE h.lane BETWEEN 1 AND 6
                 AND h.racer_number IS NOT NULL
                 AND h.start_course BETWEEN 1 AND 6
                 AND h.finish_position BETWEEN 1 AND 6
                 AND h.is_flying IS FALSE
                 AND h.is_late IS FALSE)=6) AS full6
 FROM public.v2_result_entries h
 JOIN races r USING (race_id)
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
                 AND x.exhibition_time_rank BETWEEN 1 AND 6)=6) AS full6,
        (count(*) FILTER (
               WHERE x.lane BETWEEN 1 AND 6
                 AND x.exhibition_time_rank BETWEEN 1 AND 6
                 AND x.snapshot_at < r.deadline_at::timestamptz)=6)
          AS timestamps_predeadline6
 FROM boat_data.exhibition_snapshots x
 JOIN races r USING(race_id)
 GROUP BY x.race_id,x.snapshot_label
), exhibition AS MATERIALIZED (
 SELECT race_id,
        bool_or(full6) AS full6,
        bool_or(full6 AND timestamps_predeadline6) AS predeadline_shape6,
        count(*) FILTER (WHERE full6)::int AS complete_label_count
 FROM exhibition_by_label
 GROUP BY race_id
), status AS (
 SELECT r.race_id,
        coalesce(e.full6,FALSE) AS roster6,
        coalesce(k.full6,FALSE) AS k_clean6,
        coalesce(x.full6,FALSE) AS exhibition6,
        coalesce(x.predeadline_shape6,FALSE) AS exhibition_timestamp6,
        EXISTS(SELECT 1 FROM public.v2_results rs
               WHERE rs.race_id=r.race_id) AS result_exists
 FROM races r
 LEFT JOIN roster e USING(race_id)
 LEFT JOIN k USING(race_id)
 LEFT JOIN exhibition x USING(race_id)
)
SELECT :'day'::date AS inspected_day,
       count(*) AS races,
       count(*) FILTER (WHERE roster6) AS roster6,
       count(*) FILTER (WHERE k_clean6) AS k_clean6,
       count(*) FILTER (WHERE exhibition6) AS any_label_exhibition6,
       count(*) FILTER (
         WHERE exhibition6 AND exhibition_timestamp6
       ) AS any_label_timestamp_predeadline6_not_proof,
       count(*) FILTER (
         WHERE roster6 AND k_clean6 AND exhibition6 AND result_exists
       ) AS joint_source_shape6_not_proven_forward,
       count(*) FILTER (
         WHERE roster6 AND k_clean6 AND exhibition_timestamp6
               AND result_exists
       ) AS joint_timestamp_shape6_not_first_write_proof,
       count(*) FILTER (
         WHERE exhibition6 AND NOT k_clean6
       ) AS exhibition6_without_clean_k6,
       count(*) FILTER (
         WHERE k_clean6 AND NOT exhibition6
       ) AS clean_k6_without_exhibition6,
       count(*) FILTER (
         WHERE NOT exhibition6
       ) AS races_without_complete_exhibition6
FROM status;
COMMIT;
SELECT 'V5_JOINT_K_EXHIBITION_SHAPE_READONLY_HOLD_NO_MODEL_NO_BUY' AS audit;
