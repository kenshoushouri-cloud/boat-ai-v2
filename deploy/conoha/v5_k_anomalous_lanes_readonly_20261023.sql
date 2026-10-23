-- One day only: compact exception-lane details for V5 research K sources.
-- Distinguishes missing K values / abnormal finish_status from six-row shape.
-- F/L and finish_status are POSTRACE; NEVER select predeadline bets by them.
-- Uses only source K rows, boat_data VIEW, no HTTP, writes, training or BUY.
-- Run: psql -v day=2026-10-20 -f /tmp/v5_k_anomaly_lanes.sql
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
\if :{?day}
\else
\set day 2026-10-20
\endif
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='15000ms';
SET LOCAL lock_timeout='1000ms';
SET LOCAL work_mem='8MB';

WITH target AS MATERIALIZED (
  SELECT race_id
  FROM boat_data.races
  WHERE race_date=:'day'::date
    AND race_date>=DATE '2025-07-01'
), k AS MATERIALIZED (
  SELECT h.race_id,
         count(*)::int AS n,
         count(DISTINCT h.lane) FILTER (
           WHERE h.lane BETWEEN 1 AND 6)::int AS lane_n,
         count(DISTINCT h.start_course) FILTER (
           WHERE h.start_course BETWEEN 1 AND 6)::int AS course_n,
         count(*) FILTER (
           WHERE h.lane BETWEEN 1 AND 6
             AND h.racer_number IS NOT NULL
             AND h.start_course BETWEEN 1 AND 6
             AND h.finish_position BETWEEN 1 AND 6
             AND h.is_flying IS FALSE AND h.is_late IS FALSE
         )::int AS clean_n,
         count(*) FILTER (
           WHERE h.is_flying IS TRUE OR h.is_late IS TRUE
         )::int AS fl_n,
         count(*) FILTER (
           WHERE h.is_flying IS NULL OR h.is_late IS NULL
         )::int AS unknown_fl_n,
         string_agg(
           format('L%s:C%s/F%s/S%s',
             coalesce(h.lane::text,'?'),
             coalesce(h.start_course::text,'?'),
             coalesce(h.finish_position::text,'?'),
             left(coalesce(nullif(h.finish_status::text,''),'?'),14)),
           '; ' ORDER BY h.lane
         ) FILTER (
           WHERE h.lane IS NULL OR h.lane NOT BETWEEN 1 AND 6
              OR h.racer_number IS NULL
              OR h.start_course IS NULL OR h.start_course NOT BETWEEN 1 AND 6
              OR h.finish_position IS NULL OR h.finish_position NOT BETWEEN 1 AND 6
              OR h.is_flying IS DISTINCT FROM FALSE
              OR h.is_late IS DISTINCT FROM FALSE
         ) AS anomalous_lanes,
         string_agg(coalesce(h.start_course::text,'?'),
                    ',' ORDER BY h.lane) AS all_courses
  FROM public.v2_result_entries h
  JOIN target t USING(race_id)
  WHERE h.source='official_k_file'
  GROUP BY h.race_id
), ex AS MATERIALIZED (
  SELECT race_id, bool_or(valid6) AS complete6
  FROM (
    SELECT x.race_id, x.snapshot_label,
           (count(*)=6
            AND count(DISTINCT x.lane) FILTER (
              WHERE x.lane BETWEEN 1 AND 6
                AND x.exhibition_time_rank BETWEEN 1 AND 6)=6
            AND count(DISTINCT x.exhibition_time_rank) FILTER (
              WHERE x.lane BETWEEN 1 AND 6
                AND x.exhibition_time_rank BETWEEN 1 AND 6)=6) AS valid6
    FROM boat_data.exhibition_snapshots x
    JOIN target t USING(race_id)
    GROUP BY x.race_id,x.snapshot_label
  ) labels
  GROUP BY race_id
)
SELECT t.race_id,
       CASE WHEN coalesce(ex.complete6,false) THEN 'Y' ELSE 'N' END AS exh6,
       CASE WHEN coalesce(k.n,0)=0 THEN 'NO_K'
            WHEN k.n<>6 THEN 'K_ROWS'
            WHEN k.lane_n<>6 THEN 'K_LANES'
            WHEN k.fl_n>0 THEN 'F_OR_L'
            WHEN k.unknown_fl_n>0 THEN 'F_L_UNKNOWN'
            WHEN k.course_n<>6 THEN 'COURSE'
            WHEN k.clean_n<>6 THEN 'FINISH_OR_STATUS'
            ELSE 'OTHER' END AS k_reason,
       coalesce(k.anomalous_lanes,'(none)') AS abnormal_k_lanes,
       coalesce(k.all_courses,'?') AS course_sequence
FROM target t
LEFT JOIN k USING(race_id)
LEFT JOIN ex USING(race_id)
WHERE NOT (coalesce(k.n,0)=6
       AND k.lane_n=6 AND k.course_n=6 AND k.clean_n=6)
ORDER BY coalesce(ex.complete6,false) DESC,t.race_id
LIMIT 20;

COMMIT;
SELECT 'V5_BAD_K_LANES_READONLY_RETROSPECTIVE_ONLY_NO_BUY' AS audit;
