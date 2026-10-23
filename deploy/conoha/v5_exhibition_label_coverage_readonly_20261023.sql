-- V5 one-day exhibition snapshot-label coverage, read-only.
-- Why: on 2026-10-20 the 'historical' label had 0/144 complete
--      six-lane snapshots, but other labels may exist.
-- This is a research-source inventory, NOT first-observation proof.
-- No collector changes, writes, migrations, feature fitting, or BUY.
-- psql -v day=2026-10-20 -f /tmp/v5_exhibition_labels.sql
\set ON_ERROR_STOP on
\pset pager off
\if :{?day}
\else
\set day 2026-10-20
\endif
BEGIN TRANSACTION READ ONLY;
SET LOCAL lock_timeout='1000ms';
SET LOCAL statement_timeout='15000ms';
SET LOCAL work_mem='8MB';

WITH target AS MATERIALIZED (
  SELECT race_id, deadline_at
  FROM boat_data.races
  WHERE race_date=:'day'::date
    AND race_date >= DATE '2025-07-01'
), same_label AS MATERIALIZED (
  SELECT x.race_id,
         coalesce(x.snapshot_label,'(NULL)') AS label,
         count(*)::integer AS boat_rows,
         count(DISTINCT x.lane) FILTER (
           WHERE x.lane BETWEEN 1 AND 6
             AND x.exhibition_time_rank BETWEEN 1 AND 6
         )::integer AS valid_lanes,
         count(DISTINCT x.exhibition_time_rank) FILTER (
           WHERE x.lane BETWEEN 1 AND 6
             AND x.exhibition_time_rank BETWEEN 1 AND 6
         )::integer AS valid_ranks,
         count(*) FILTER (
           WHERE x.lane BETWEEN 1 AND 6
             AND x.exhibition_time_rank BETWEEN 1 AND 6
             AND x.snapshot_at < t.deadline_at::timestamptz
         )::integer AS timestamp_predeadline_rows
  FROM boat_data.exhibition_snapshots x
  JOIN target t ON t.race_id=x.race_id
  GROUP BY x.race_id,x.snapshot_label
), grouped AS (
  SELECT race_id,boat_rows,valid_lanes,valid_ranks,
         timestamp_predeadline_rows,
         CASE
           WHEN label='historical' THEN 'historical'
           WHEN label LIKE 'conoha_forward_%' THEN 'conoha_forward_*'
           WHEN label LIKE 'conoha_%' THEN 'conoha_other_*'
           ELSE label
         END AS label_family
  FROM same_label
)
SELECT :'day'::date AS inspected_day,
       CASE WHEN GROUPING(label_family)=1
            THEN 'ALL_LABELS' ELSE label_family END AS label_family,
       count(DISTINCT race_id)::integer AS races_with_rows,
       coalesce(sum(boat_rows),0)::integer AS stored_boat_rows,
       count(*) FILTER (
         WHERE boat_rows=6 AND valid_lanes=6 AND valid_ranks=6
       )::integer AS complete_6_snapshots,
       count(DISTINCT race_id) FILTER (
         WHERE boat_rows=6 AND valid_lanes=6 AND valid_ranks=6
       )::integer AS races_with_complete_6,
       count(DISTINCT race_id) FILTER (
         WHERE boat_rows=6 AND valid_lanes=6 AND valid_ranks=6
           AND timestamp_predeadline_rows=6
       )::integer AS timestamp_predeadline_6_not_first_write_proof
FROM grouped
GROUP BY ROLLUP(label_family)
ORDER BY GROUPING(label_family) DESC,
         stored_boat_rows DESC,
         label_family
LIMIT 20;

COMMIT;
SELECT 'V5_EXHIBITION_LABELS_READONLY_NO_FIT_NO_FIRST_WRITE_PROOF_NO_BUY' AS audit;
