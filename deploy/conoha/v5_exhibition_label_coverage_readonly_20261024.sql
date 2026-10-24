-- V5 research-only: single-day exhibition snapshot label inventory.
-- Motivation: 2026-10-20 had 144 races but ZERO complete 'historical'
-- labels in the strict source-coverage pilot. Other labels might be available.
-- A timestamp/6-row shape is NOT proof of original first observation.
-- Bounded/READ ONLY; NO repair, model run, staging, BUY or network access.
-- psql -v day=2026-10-20 -f <this file>
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

WITH day_races AS MATERIALIZED (
  SELECT race_id,deadline_at::timestamptz AS deadline_at
  FROM boat_data.races
  WHERE race_date=:'day'::date AND race_date>=DATE '2025-07-01'
), per_label AS MATERIALIZED (
  SELECT x.race_id,
         x.snapshot_label,
         count(*)::int AS rows_n,
         count(DISTINCT x.lane) FILTER (
           WHERE x.lane BETWEEN 1 AND 6
             AND x.exhibition_time IS NOT NULL
             AND x.exhibition_time_rank BETWEEN 1 AND 6
         )::int AS valid_lanes_n,
         count(DISTINCT x.exhibition_time_rank) FILTER (
           WHERE x.lane BETWEEN 1 AND 6
             AND x.exhibition_time IS NOT NULL
             AND x.exhibition_time_rank BETWEEN 1 AND 6
         )::int AS valid_ranks_n,
         count(*) FILTER (
           WHERE x.snapshot_at < r.deadline_at
         )::int AS labeled_before_deadline_n
  FROM day_races r
  JOIN boat_data.exhibition_snapshots x USING(race_id)
  GROUP BY x.race_id,x.snapshot_label
), grouped AS (
  SELECT race_id,snapshot_label,rows_n,valid_lanes_n,valid_ranks_n,
         labeled_before_deadline_n,
         CASE
           WHEN snapshot_label IS NULL THEN 'NULL_LABEL'
           WHEN snapshot_label='historical' THEN 'historical'
           WHEN snapshot_label='final_ab' THEN 'final_ab'
           WHEN snapshot_label='learning_all' THEN 'learning_all'
           WHEN snapshot_label LIKE 'conoha_forward_%' THEN 'conoha_forward'
           ELSE 'other'
         END AS label_group
  FROM per_label
)
SELECT :'day'::date AS inspected_day, label_group,
       count(*)::int AS race_label_groups,
       count(DISTINCT race_id)::int AS races_with_any,
       count(DISTINCT snapshot_label)::int AS distinct_labels,
       sum(rows_n)::bigint AS rows_total,
       count(DISTINCT race_id) FILTER (
         WHERE rows_n=6 AND valid_lanes_n=6 AND valid_ranks_n=6
       )::int AS races_complete_six,
       count(DISTINCT race_id) FILTER (
         WHERE rows_n=6 AND valid_lanes_n=6 AND valid_ranks_n=6
           AND labeled_before_deadline_n=6
       )::int AS labeled_predeadline_six_NOT_first_capture_proof,
       min(snapshot_label) AS sample_first_label
FROM grouped
GROUP BY label_group
ORDER BY label_group;

ROLLBACK;
SELECT 'V5_EXHIBITION_LABEL_AUDIT_READ_ONLY_NO_MODEL_NO_BUY' AS audit;
