-- V5 retrospective exhibition coverage probe: SIX fixed sample days only.
-- Does not certify true first observation, pre-decision receipt, or real ROI.
-- No changes to existing data or collector. Only boat_data source views.
\set ON_ERROR_STOP on
\pset pager off

BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='15000ms';
SET LOCAL lock_timeout='1000ms';
SET LOCAL work_mem='8MB';

WITH sample_days(day) AS (
  VALUES
    (DATE '2025-07-15'),
    (DATE '2025-10-15'),
    (DATE '2026-01-15'),
    (DATE '2026-04-15'),
    (DATE '2026-07-15'),
    (DATE '2026-10-20')
), races AS MATERIALIZED (
  SELECT r.race_date, r.race_id, r.deadline_at::timestamptz AS deadline_at
  FROM boat_data.races r
  JOIN sample_days s ON s.day=r.race_date
), per_label AS MATERIALIZED (
  SELECT r.race_date, r.race_id, x.snapshot_label,
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
           WHERE x.snapshot_at<r.deadline_at
         )::int AS nominal_predeadline_rows
  FROM races r
  JOIN boat_data.exhibition_snapshots x ON x.race_id=r.race_id
  GROUP BY r.race_date,r.race_id,x.snapshot_label
), flags AS (
  SELECT race_date,race_id,snapshot_label,
         (rows_n=6 AND valid_lanes_n=6 AND valid_ranks_n=6) AS complete6,
         (rows_n=6 AND valid_lanes_n=6 AND valid_ranks_n=6
           AND nominal_predeadline_rows=6) AS nominal_predeadline6
  FROM per_label
), totals AS (
  SELECT race_date,count(*)::int AS race_total
  FROM races GROUP BY race_date
), counts AS (
  SELECT race_date,
         count(DISTINCT race_id)::int AS races_with_any,
         count(DISTINCT race_id) FILTER (
           WHERE complete6
         )::int AS complete_any_label,
         count(DISTINCT race_id) FILTER (
           WHERE complete6 AND snapshot_label='historical'
         )::int AS historical_6,
         count(DISTINCT race_id) FILTER (
           WHERE complete6 AND snapshot_label='final_ab'
         )::int AS final_ab_6,
         count(DISTINCT race_id) FILTER (
           WHERE complete6 AND snapshot_label='learning_all'
         )::int AS learning_all_6,
         count(DISTINCT race_id) FILTER (
           WHERE complete6 AND snapshot_label LIKE 'conoha_forward_%'
         )::int AS forward_6,
         count(DISTINCT race_id) FILTER (
           WHERE complete6 AND (
             snapshot_label IS NULL OR snapshot_label NOT IN
             ('historical','final_ab','learning_all')
             AND snapshot_label NOT LIKE 'conoha_forward_%'
           )
         )::int AS other_6,
         count(DISTINCT race_id) FILTER (
           WHERE nominal_predeadline6
         )::int AS nominal_before_deadline_NOT_PROOF
  FROM flags GROUP BY race_date
)
SELECT s.day AS inspected_day,
       coalesce(t.race_total,0) AS races,
       coalesce(c.races_with_any,0) AS ex_races_any,
       coalesce(c.complete_any_label,0) AS six_any,
       coalesce(c.historical_6,0) AS hist6,
       coalesce(c.final_ab_6,0) AS final6,
       coalesce(c.learning_all_6,0) AS learn6,
       coalesce(c.forward_6,0) AS forward6,
       coalesce(c.other_6,0) AS other6,
       coalesce(c.nominal_before_deadline_NOT_PROOF,0) AS time6_NOT_PROOF
FROM sample_days s
LEFT JOIN totals t ON t.race_date=s.day
LEFT JOIN counts c ON c.race_date=s.day
ORDER BY s.day;

ROLLBACK;
SELECT 'V5_EXHIBITION_6_DATES_READ_ONLY_NO_BUY' AS audit;
