-- V5 cutover timing preflight, 2026-10-22 JST. Read-only, no writes.
-- Evidence of data availability must precede deadline; never substitute
-- postrace historical data for time-frozen snapshots.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL TIME ZONE 'Asia/Tokyo';
SET LOCAL statement_timeout = '15000ms';
SET LOCAL lock_timeout = '1500ms';
WITH day_races AS MATERIALIZED (
  SELECT race_id, deadline_at::timestamptz AS cutoff_jst
  FROM public.v2_races
  WHERE race_date = DATE '2026-10-22' AND deadline_at IS NOT NULL
)
SELECT 'V5_DAY_DEADLINE_GATE' AS audit,
       COUNT(*) AS races_with_deadline,
       TO_CHAR(MAX(cutoff_jst), 'YYYY-MM-DD HH24:MI:SS TZ') AS last_cutoff_jst,
       COUNT(*) FILTER (WHERE cutoff_jst > CURRENT_TIMESTAMP) AS future_cutoffs,
       CASE
         WHEN COUNT(*) = 0 THEN 'STOP_NO_RACES'
         WHEN COUNT(*) FILTER (WHERE cutoff_jst > CURRENT_TIMESTAMP) > 0 THEN 'STOP_RACES_STILL_OPEN'
         ELSE 'ALL_KNOWN_DEADLINES_PASSED_NOT_CAPTURE_PROOF'
       END AS verdict
FROM day_races;
WITH last_races AS MATERIALIZED (
  SELECT race_id, deadline_at::timestamptz AS cutoff_jst
  FROM public.v2_races
  WHERE race_date = DATE '2026-10-22' AND deadline_at IS NOT NULL
  ORDER BY deadline_at::timestamptz DESC, race_id DESC
  LIMIT 12
)
SELECT 'V5_LAST_RACE_SNAPSHOTS' AS audit, r.race_id,
       TO_CHAR(r.cutoff_jst, 'HH24:MI:SS') AS cutoff_jst,
       COALESCE(ex.lanes,0) AS best_predeadline_exhibition_lanes,
       COALESCE(od.tickets,0) AS best_predeadline_positive_odds,
       CASE
         WHEN r.cutoff_jst > CURRENT_TIMESTAMP THEN 'RACE_NOT_YET_CLOSED'
         WHEN COALESCE(ex.lanes,0)=6 AND COALESCE(od.tickets,0)=120 THEN 'SNAPSHOT_COUNTS_OK'
         ELSE 'INCOMPLETE_SNAPSHOT_KEEP_MISSING_FLAG'
       END AS verdict
FROM last_races r
LEFT JOIN LATERAL (
  SELECT MAX(lanes) AS lanes FROM (
    SELECT COUNT(DISTINCT e.lane) AS lanes
    FROM public.v2_realtime_exhibition_snapshots e
    WHERE e.race_id=r.race_id AND e.exhibition_time IS NOT NULL
      AND e.snapshot_at < r.cutoff_jst
    GROUP BY e.snapshot_label
  ) labels
) ex ON TRUE
LEFT JOIN LATERAL (
  SELECT MAX(tickets) AS tickets FROM (
    SELECT COUNT(DISTINCT o.ticket) AS tickets
    FROM public.v2_realtime_odds_snapshots o
    WHERE o.race_id=r.race_id AND o.odds > 0
      AND o.snapshot_at < r.cutoff_jst
    GROUP BY o.snapshot_label
  ) labels
) od ON TRUE
ORDER BY r.cutoff_jst DESC, r.race_id DESC;
COMMIT;
SELECT 'V5_LAST_RACES_SNAPSHOT_AUDIT_READONLY_DONE_NO_DB_WRITES' AS verdict;
