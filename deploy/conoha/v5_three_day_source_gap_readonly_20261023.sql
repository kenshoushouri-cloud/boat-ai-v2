-- V5 source-shape trend across EXACTLY 3 contiguous dates; READ ONLY.
-- Bounded fixed window: 2026-10-18..2026-10-20. No runtime date override.
-- Result incidents are POSTRACE facts (for historical diagnosis only).
-- This does NOT prove official refunds, immutable first observation, early
-- exhibition access, research fit eligibility, Forward, ROI, or BUY.
-- 13 boat_data relations remain non-updatable VIEWs; no INSERT/DDL/COPY.
-- Usage: psql -d railway -X -v ON_ERROR_STOP=1 -f /tmp/v5_3day_sources.sql
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
BEGIN TRANSACTION READ ONLY;
SET LOCAL lock_timeout='1000ms';
SET LOCAL statement_timeout='20000ms';
SET LOCAL work_mem='8MB';

WITH days AS MATERIALIZED (
 SELECT generate_series(DATE '2026-10-18',DATE '2026-10-20',
                        INTERVAL '1 day')::date AS day
), races AS MATERIALIZED (
 SELECT race_id,race_date,deadline_at
 FROM boat_data.races
 WHERE race_date BETWEEN DATE '2026-10-18' AND DATE '2026-10-20'
   AND race_date >= DATE '2025-07-01'
), entries AS MATERIALIZED (
 SELECT e.race_id,
        (count(*)=6
         AND count(DISTINCT e.lane) FILTER (
           WHERE e.lane BETWEEN 1 AND 6)=6
         AND count(DISTINCT e.racer_number) FILTER (
           WHERE e.racer_number IS NOT NULL)=6
         AND count(*) FILTER (
           WHERE e.lane BETWEEN 1 AND 6
             AND e.racer_number IS NOT NULL
             AND e.racer_class IS NOT NULL
             AND trim(e.racer_class::text)<>'')=6) AS full6
 FROM boat_data.entries e JOIN races r USING (race_id)
 GROUP BY e.race_id
), k AS MATERIALIZED (
 SELECT h.race_id,
        count(*)::integer AS rows_n,
        count(DISTINCT h.lane) FILTER (
          WHERE h.lane BETWEEN 1 AND 6)::integer AS lanes_n,
        count(DISTINCT h.start_course) FILTER (
          WHERE h.start_course BETWEEN 1 AND 6)::integer AS course_n,
        count(*) FILTER (
          WHERE h.lane BETWEEN 1 AND 6
            AND h.racer_number IS NOT NULL
            AND h.start_course BETWEEN 1 AND 6
            AND h.finish_position BETWEEN 1 AND 6
            AND h.is_flying IS FALSE
            AND h.is_late IS FALSE)::integer AS clean_n,
        count(*) FILTER (
          WHERE h.is_flying IS TRUE OR h.is_late IS TRUE
        )::integer AS fl_n,
        count(*) FILTER (
          WHERE h.is_flying IS NULL OR h.is_late IS NULL
        )::integer AS fl_unknown_n
 FROM public.v2_result_entries h JOIN races r USING(race_id)
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
        count(*) FILTER (
          WHERE x.lane BETWEEN 1 AND 6
            AND x.exhibition_time_rank BETWEEN 1 AND 6
            AND x.snapshot_at < r.deadline_at::timestamptz
        )=6 AS timestamp_before_deadline6
 FROM boat_data.exhibition_snapshots x
 JOIN races r USING(race_id)
 GROUP BY x.race_id,x.snapshot_label
), exhibition AS MATERIALIZED (
 SELECT race_id,
        bool_or(full6) AS full6,
        bool_or(full6 AND timestamp_before_deadline6) AS before_deadline6
 FROM exhibition_by_label GROUP BY race_id
), status AS MATERIALIZED (
 SELECT r.race_date AS day,r.race_id,
        coalesce(e.full6,false) AS roster6,
        (coalesce(k.rows_n,0)=6 AND coalesce(k.lanes_n,0)=6
          AND coalesce(k.course_n,0)=6 AND coalesce(k.clean_n,0)=6)
          AS clean_k6,
        coalesce(x.full6,false) AS exhibition6,
        coalesce(x.before_deadline6,false) AS exhibition_timestamp6,
        EXISTS(SELECT 1 FROM public.v2_results rs
               WHERE rs.race_id=r.race_id) AS has_result,
        CASE
          WHEN coalesce(k.rows_n,0)=0 THEN 'NO_K'
          WHEN k.rows_n<>6 OR k.lanes_n<>6 THEN 'K_ROWS_OR_LANES'
          WHEN k.fl_n>0 THEN 'K_F_OR_L'
          WHEN k.fl_unknown_n>0 THEN 'K_F_L_UNKNOWN'
          WHEN k.course_n<>6 THEN 'K_COURSE'
          WHEN k.clean_n<>6 THEN 'K_FINISH_OR_FIELDS'
          ELSE 'K_CLEAN_SHAPE'
        END AS k_reason,
        CASE
          WHEN x.race_id IS NULL THEN 'NO_EX_ROWS'
          WHEN x.full6 IS NOT TRUE THEN 'EX_PARTIAL'
          WHEN x.before_deadline6 IS NOT TRUE THEN 'EX_TIMESTAMP_LATE'
          ELSE 'EX_TIMESTAMP_BEFORE_NOT_PROOF'
        END AS ex_reason
 FROM races r
 LEFT JOIN entries e USING(race_id)
 LEFT JOIN k USING(race_id)
 LEFT JOIN exhibition x USING(race_id)
), census AS (
 SELECT d.day, count(s.race_id)::integer AS races,
        count(*) FILTER (WHERE roster6)::integer AS roster6,
        count(*) FILTER (WHERE has_result)::integer AS result_present,
        count(*) FILTER (WHERE clean_k6)::integer AS k6,
        count(*) FILTER (WHERE exhibition6)::integer AS exhibition6,
        count(*) FILTER (
          WHERE roster6 AND clean_k6 AND exhibition6 AND has_result
        )::integer AS joint6,
        count(*) FILTER (
          WHERE clean_k6 AND NOT exhibition6
        )::integer AS k_without_ex,
        count(*) FILTER (
          WHERE exhibition6 AND NOT clean_k6
        )::integer AS ex_without_k,
        count(*) FILTER (WHERE k_reason='NO_K')::integer AS no_k,
        count(*) FILTER (
          WHERE k_reason='K_ROWS_OR_LANES')::integer AS k_row_lanes,
        count(*) FILTER (WHERE k_reason='K_F_OR_L')::integer AS k_fl,
        count(*) FILTER (WHERE k_reason='K_F_L_UNKNOWN')::integer AS k_fl_unk,
        count(*) FILTER (WHERE k_reason='K_COURSE')::integer AS k_course,
        count(*) FILTER (
          WHERE k_reason='K_FINISH_OR_FIELDS')::integer AS k_finish,
        count(*) FILTER (WHERE ex_reason='NO_EX_ROWS')::integer AS no_ex,
        count(*) FILTER (WHERE ex_reason='EX_PARTIAL')::integer AS ex_partial,
        count(*) FILTER (
          WHERE ex_reason='EX_TIMESTAMP_LATE')::integer AS ex_late,
        count(*) FILTER (
          WHERE exhibition6 AND exhibition_timestamp6
        )::integer AS predeadline_label_not_proof
 FROM days d LEFT JOIN status s ON s.day=d.day
 GROUP BY d.day
)
SELECT to_char(day,'YYYY-MM-DD') AS day,
       format('races=%s roster6=%s results=%s K6=%s ex6=%s joint6=%s',
              races,roster6,result_present,k6,exhibition6,joint6)
              AS structural_coverage_not_fit,
       format('K_only=%s ex_only=%s no_K=%s K_rows=%s F_L=%s FL_unknown=%s K_course=%s K_finish=%s',
              k_without_ex,ex_without_k,no_k,k_row_lanes,
              k_fl,k_fl_unk,k_course,k_finish)
              AS official_k_reason_not_predecision,
       format('no_ex=%s partial_ex=%s late_ex=%s timestamp6=%s_NOT_FIRST_WRITE_PROOF',
              no_ex,ex_partial,ex_late,predeadline_label_not_proof)
              AS exhibition_reason_not_first_write
FROM census
ORDER BY day;
COMMIT;
SELECT 'V5_THREE_DAY_SOURCE_GAP_READONLY_HOLD_NO_FIT_NO_BUY' AS audit;
