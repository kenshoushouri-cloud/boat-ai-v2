-- V5 exhibit as-of candidate check. Railway candidate-v4 Data > Query ONLY.
-- Single read-only SELECT, 2025-07-01 only, verified Q1 144 distinct.
-- learning_all/final_ab only; catalog-indexed race_id+snapshot_label join.
-- No individual race IDs, Q3/results/odds, raw JSON, UPDATE/DDL.
-- Predeadline snapshot_at is NOT proof of original capture or real ROI.
WITH races AS MATERIALIZED (
  SELECT race_id, deadline_at FROM public.v2_races
  WHERE race_date = DATE '2025-07-01'
),
q1 AS (
  SELECT count(*)::bigint n, count(race_id)::bigint nonnull,
         count(DISTINCT race_id)::bigint unique_ids FROM races
),
candidate AS MATERIALIZED (
  SELECT r.race_id, r.deadline_at, x.snapshot_label, x.lane,
         x.exhibition_time_rank, x.snapshot_at
  FROM races r
  JOIN public.v2_realtime_exhibition_snapshots x
    ON x.race_id = r.race_id
   AND x.snapshot_label IN ('learning_all','final_ab')
  CROSS JOIN q1
  WHERE q1.n=144 AND q1.nonnull=144 AND q1.unique_ids=144
),
per_race_label AS (
  SELECT race_id, snapshot_label, count(*)::bigint rows_found,
         count(DISTINCT lane) FILTER (WHERE lane BETWEEN 1 AND 6) lanes,
         count(*) FILTER (
           WHERE lane BETWEEN 1 AND 6 AND snapshot_at<deadline_at
             AND exhibition_time_rank BETWEEN 1 AND 6
         ) before_rows,
         count(DISTINCT lane) FILTER (
           WHERE lane BETWEEN 1 AND 6 AND snapshot_at<deadline_at
             AND exhibition_time_rank BETWEEN 1 AND 6
         ) before_lanes,
         count(DISTINCT exhibition_time_rank) FILTER (
           WHERE lane BETWEEN 1 AND 6 AND snapshot_at<deadline_at
             AND exhibition_time_rank BETWEEN 1 AND 6
         ) before_distinct_ranks,
         count(*) FILTER (WHERE snapshot_at>=deadline_at) late_rows,
         count(*) FILTER (WHERE snapshot_at IS NULL) unknown_time_rows
  FROM candidate GROUP BY race_id,snapshot_label
),
summarized AS (
  SELECT snapshot_label, sum(rows_found)::bigint rows_found,
         sum(before_rows)::bigint before_rows, sum(late_rows)::bigint late_rows,
         sum(unknown_time_rows)::bigint unknown_time_rows,
         count(*) FILTER (
           WHERE rows_found=6 AND lanes=6 AND before_rows=6
             AND before_lanes=6 AND before_distinct_ranks=6
             AND late_rows=0 AND unknown_time_rows=0
         )::bigint complete_predeadline_races
  FROM per_race_label GROUP BY snapshot_label
),
rollup AS (
  SELECT q1.n AS q1_rows, q1.unique_ids,
         coalesce(sum(s.rows_found) FILTER (WHERE snapshot_label='learning_all'),0) AS learning_rows,
         coalesce(sum(s.before_rows) FILTER (WHERE snapshot_label='learning_all'),0) AS learning_before_rows,
         coalesce(sum(s.late_rows) FILTER (WHERE snapshot_label='learning_all'),0) AS learning_late_rows,
         coalesce(sum(s.complete_predeadline_races) FILTER (WHERE snapshot_label='learning_all'),0) AS learning_complete_predeadline_races,
         coalesce(sum(s.rows_found) FILTER (WHERE snapshot_label='final_ab'),0) AS final_rows,
         coalesce(sum(s.before_rows) FILTER (WHERE snapshot_label='final_ab'),0) AS final_before_rows,
         coalesce(sum(s.late_rows) FILTER (WHERE snapshot_label='final_ab'),0) AS final_late_rows,
         coalesce(sum(s.complete_predeadline_races) FILTER (WHERE snapshot_label='final_ab'),0) AS final_complete_predeadline_races
  FROM q1 LEFT JOIN summarized s ON TRUE
  GROUP BY q1.n,q1.unique_ids
)
SELECT DATE '2025-07-01' AS race_date_checked, q1_rows, unique_ids,
       learning_rows, learning_before_rows, learning_late_rows, learning_complete_predeadline_races,
       final_rows, final_before_rows, final_late_rows, final_complete_predeadline_races,
       CASE WHEN q1_rows<>144 OR unique_ids<>144 THEN 'HOLD_Q1_CHANGED'
            WHEN learning_complete_predeadline_races=0 AND final_complete_predeadline_races=0
              THEN 'NO_COMPLETE_PREDEADLINE_LABEL_EVIDENCE'
            ELSE 'TIMESTAMP_CANDIDATES_NOT_ORIGINAL_CAPTURE_PROOF'
       END AS asof_verdict,
       'NO_Q3_ROI_FORWARD_OR_BUY_AUTHORIZATION'::text AS authorization
FROM rollup;
