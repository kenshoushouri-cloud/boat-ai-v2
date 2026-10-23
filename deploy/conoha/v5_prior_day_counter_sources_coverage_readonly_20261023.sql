-- V5 research-only: bounded one-day source coverage for 13 prior-day Counters.
-- NO counter build or training; no UPDATE/DDL/HTTP/BUY; no "forward eligible".
-- Sources: boat_data VIEWS, official K result entries, historical exhibition.
-- WARNING: postrace K incident filters are retrospective training eligibility ONLY.
-- Historical exhibition labels/timestamps are mutable and NOT first-write proof.
-- psql -v day=2026-10-20 -f /tmp/v5_counter_sources_coverage.sql
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

WITH r AS MATERIALIZED (
  SELECT race_id,race_date,deadline_at
  FROM boat_data.races
  WHERE race_date = :'day'::date
    AND race_date >= DATE '2025-07-01'
), e AS MATERIALIZED (
  SELECT t.race_id,
         count(*)::int AS rows_n,
         count(DISTINCT t.lane) FILTER (WHERE t.lane BETWEEN 1 AND 6)::int AS lanes_n,
         count(DISTINCT t.racer_number) FILTER (WHERE t.racer_number IS NOT NULL)::int AS racers_n,
         count(*) FILTER (
           WHERE t.lane BETWEEN 1 AND 6 AND t.racer_number IS NOT NULL
             AND t.racer_class IS NOT NULL AND trim(t.racer_class::text)<>''
         )::int AS valid_class_n
  FROM boat_data.entries t JOIN r USING(race_id)
  GROUP BY t.race_id
), x AS MATERIALIZED (
  SELECT t.race_id,
         count(*)::int AS rows_n,
         count(DISTINCT t.lane) FILTER (
           WHERE t.lane BETWEEN 1 AND 6
             AND t.exhibition_time_rank BETWEEN 1 AND 6
         )::int AS valid_lanes_n,
         count(DISTINCT t.exhibition_time_rank) FILTER (
           WHERE t.exhibition_time_rank BETWEEN 1 AND 6
         )::int AS unique_ranks_n,
         count(*) FILTER (
           WHERE t.snapshot_at < r.deadline_at::timestamptz
         )::int AS labeled_before_deadline_n
  FROM boat_data.exhibition_snapshots t JOIN r USING(race_id)
  WHERE t.snapshot_label='historical'
  GROUP BY t.race_id
), k AS MATERIALIZED (
  SELECT h.race_id,
         count(*)::int AS rows_n,
         count(DISTINCT h.lane) FILTER (WHERE h.lane BETWEEN 1 AND 6)::int AS lanes_n,
         count(DISTINCT h.start_course) FILTER (
           WHERE h.start_course BETWEEN 1 AND 6
         )::int AS distinct_course_n,
         count(*) FILTER (
           WHERE h.lane BETWEEN 1 AND 6
             AND h.racer_number IS NOT NULL
             AND h.start_course BETWEEN 1 AND 6
             AND h.finish_position BETWEEN 1 AND 6
             AND h.is_flying IS FALSE AND h.is_late IS FALSE
         )::int AS clean_finish_n
  FROM public.v2_result_entries h JOIN r USING(race_id)
  WHERE h.source='official_k_file'
  GROUP BY h.race_id
), state AS (
  SELECT r.race_id,
         (coalesce(e.rows_n,0)=6 AND coalesce(e.lanes_n,0)=6
          AND coalesce(e.racers_n,0)=6 AND coalesce(e.valid_class_n,0)=6)
          AS complete_roster,
         (coalesce(x.rows_n,0)=6 AND coalesce(x.valid_lanes_n,0)=6
          AND coalesce(x.unique_ranks_n,0)=6)
          AS historical_exrank_shape,
         (coalesce(k.rows_n,0)=6 AND coalesce(k.lanes_n,0)=6
          AND coalesce(k.distinct_course_n,0)=6
          AND coalesce(k.clean_finish_n,0)=6)
          AS clean_k_course_shape,
         EXISTS(SELECT 1 FROM public.v2_results z WHERE z.race_id=r.race_id)
          AS result_exists,
         coalesce(x.labeled_before_deadline_n,0) AS before_deadline_n
  FROM r
  LEFT JOIN e USING(race_id)
  LEFT JOIN x USING(race_id)
  LEFT JOIN k USING(race_id)
)
SELECT :'day'::date AS inspected_day,
       count(*) AS race_total,
       count(*) FILTER (WHERE complete_roster) AS roster_6,
       count(*) FILTER (WHERE historical_exrank_shape) AS historic_exrank_6,
       count(*) FILTER (WHERE clean_k_course_shape) AS clean_k_course_6,
       count(*) FILTER (WHERE result_exists) AS results_present,
       count(*) FILTER (
         WHERE complete_roster AND historical_exrank_shape
           AND clean_k_course_shape AND result_exists
       ) AS model_training_source_shape_6,
       count(*) FILTER (
         WHERE historical_exrank_shape AND before_deadline_n=6
       ) AS historical_label_timestamp_predeadline_6_not_proof
FROM state;

COMMIT;
SELECT 'V5_PRIOR_COUNTER_SOURCE_COVERAGE_READONLY_NO_MODEL_NO_BUY' AS audit;
