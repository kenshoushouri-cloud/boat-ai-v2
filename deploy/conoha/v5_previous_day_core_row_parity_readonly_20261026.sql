-- V5 previous-day core records: physical source ↔ physical stage equality.
-- STRICTLY READ ONLY. As-of ONE REPEATABLE READ snapshot in this session.
-- Checks yesterday JST (relative to execution date), no table mutations.
-- Limited to 4 core relations (races, results, entries, racer_results).
-- Does NOT prove all 13 tables, first-capture provenance, future CDC,
-- independent disaster recovery, production route readiness, or real ROI.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL TIME ZONE 'Asia/Tokyo';
SET LOCAL statement_timeout = '45000ms';
SET LOCAL lock_timeout = '1500ms';
SET LOCAL work_mem = '8MB';

WITH day AS (
  SELECT to_char(current_date - 1, 'YYYYMMDD') || '_' AS race_prefix
),
races_source AS (
  SELECT s.* FROM public.v2_races s CROSS JOIN day
  WHERE left(s.race_id::text, 9) = day.race_prefix
),
races_stage AS (
  SELECT s.* FROM boat_data_stage.races s CROSS JOIN day
  WHERE left(s.race_id::text, 9) = day.race_prefix
),
race_check AS (
 SELECT 'races'::text AS family,
  count(s.race_id)::bigint AS source_rows,
  count(d.race_id)::bigint AS stage_rows,
  count(*) FILTER (WHERE s.race_id IS NOT NULL AND d.race_id IS NULL)::bigint AS missing_stage,
  count(*) FILTER (WHERE s.race_id IS NULL AND d.race_id IS NOT NULL)::bigint AS extra_stage,
  count(*) FILTER (WHERE s.race_id IS NOT NULL AND d.race_id IS NOT NULL
     AND to_jsonb(s) IS DISTINCT FROM to_jsonb(d))::bigint AS mismatched_rows
 FROM races_source s FULL OUTER JOIN races_stage d USING (race_id)
),
results_source AS (
  SELECT s.* FROM public.v2_results s CROSS JOIN day
  WHERE left(s.race_id::text, 9) = day.race_prefix
),
results_stage AS (
  SELECT s.* FROM boat_data_stage.results s CROSS JOIN day
  WHERE left(s.race_id::text, 9) = day.race_prefix
),
result_check AS (
 SELECT 'results'::text AS family,
  count(s.race_id)::bigint AS source_rows,
  count(d.race_id)::bigint AS stage_rows,
  count(*) FILTER (WHERE s.race_id IS NOT NULL AND d.race_id IS NULL)::bigint AS missing_stage,
  count(*) FILTER (WHERE s.race_id IS NULL AND d.race_id IS NOT NULL)::bigint AS extra_stage,
  count(*) FILTER (WHERE s.race_id IS NOT NULL AND d.race_id IS NOT NULL
     AND to_jsonb(s) IS DISTINCT FROM to_jsonb(d))::bigint AS mismatched_rows
 FROM results_source s FULL OUTER JOIN results_stage d USING (race_id)
),
entries_source AS (
  SELECT s.* FROM public.v2_race_entries s CROSS JOIN day
  WHERE left(s.race_id::text, 9) = day.race_prefix
),
entries_stage AS (
  SELECT s.* FROM boat_data_stage.entries s CROSS JOIN day
  WHERE left(s.race_id::text, 9) = day.race_prefix
),
entry_check AS (
 SELECT 'entries'::text AS family,
  count(s.id)::bigint AS source_rows,
  count(d.id)::bigint AS stage_rows,
  count(*) FILTER (WHERE s.id IS NOT NULL AND d.id IS NULL)::bigint AS missing_stage,
  count(*) FILTER (WHERE s.id IS NULL AND d.id IS NOT NULL)::bigint AS extra_stage,
  count(*) FILTER (WHERE s.id IS NOT NULL AND d.id IS NOT NULL
     AND to_jsonb(s) IS DISTINCT FROM to_jsonb(d))::bigint AS mismatched_rows
 FROM entries_source s FULL OUTER JOIN entries_stage d USING (id)
),
racers_source AS (
  SELECT s.* FROM public.v2_result_entries s CROSS JOIN day
  WHERE left(s.race_id::text, 9) = day.race_prefix
),
racers_stage AS (
  SELECT s.* FROM boat_data_stage.racer_results s CROSS JOIN day
  WHERE left(s.race_id::text, 9) = day.race_prefix
),
racer_check AS (
 SELECT 'racer_results'::text AS family,
  count(s.race_id)::bigint AS source_rows,
  count(d.race_id)::bigint AS stage_rows,
  count(*) FILTER (WHERE s.race_id IS NOT NULL AND d.race_id IS NULL)::bigint AS missing_stage,
  count(*) FILTER (WHERE s.race_id IS NULL AND d.race_id IS NOT NULL)::bigint AS extra_stage,
  count(*) FILTER (WHERE s.race_id IS NOT NULL AND d.race_id IS NOT NULL
     AND to_jsonb(s) IS DISTINCT FROM to_jsonb(d))::bigint AS mismatched_rows
 FROM racers_source s FULL OUTER JOIN racers_stage d
  ON s.race_id=d.race_id AND s.lane=d.lane
),
checks AS (
 SELECT * FROM race_check UNION ALL SELECT * FROM result_check
 UNION ALL SELECT * FROM entry_check UNION ALL SELECT * FROM racer_check
)
SELECT to_char(current_date - 1, 'YYYY-MM-DD') AS race_date_jst,
 family, source_rows, stage_rows, missing_stage, extra_stage, mismatched_rows,
 CASE WHEN source_rows>0 AND source_rows=stage_rows
       AND missing_stage=0 AND extra_stage=0 AND mismatched_rows=0
      THEN 'PASS_AS_OF_QUERY_SNAPSHOT'
      ELSE 'HOLD_GAP_OR_NO_SOURCE' END AS verdict
FROM checks ORDER BY family;

ROLLBACK;
SELECT 'V5_PREVIOUS_DAY_CORE_READONLY_FINISHED_NO_CUTOVER_NO_BUY' AS verdict;
