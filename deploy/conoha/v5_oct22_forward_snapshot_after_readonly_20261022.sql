-- 2026-10-22 V5 forward-window result verification, catalog-safe SELECT only.
-- Historical after-the-fact query is NOT frozen predecision evidence.
-- Strictly no data writes or service changes.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout = '12000ms';
SET LOCAL lock_timeout = '1500ms';

WITH requested(race_id) AS (
 VALUES
 ('20261022_03_03'),
 ('20261022_18_08'),
 ('20261022_11_05'),
 ('20261022_04_04'),
 ('20261022_06_04'),
 ('20261022_16_04')
), target AS (
 SELECT x.race_id, r.deadline_at::timestamptz AS cutoff
 FROM requested x
 LEFT JOIN public.v2_races r ON r.race_id=x.race_id
)
SELECT 'V5_FORWARD_AFTER_READ_ONLY' AS audit,
       r.race_id,
       CASE WHEN r.cutoff IS NULL THEN 'MISSING'
            ELSE to_char(r.cutoff AT TIME ZONE 'Asia/Tokyo','YYYY-MM-DD HH24:MI') END AS cutoff_jst,
       COALESCE(e.lanes,0) AS max_valid_exhibition_lanes,
       COALESCE(o.tickets,0) AS max_positive_odds_tickets,
       COALESCE(e.labels,0) AS exhibition_labels,
       COALESCE(o.labels,0) AS odds_labels,
       CASE WHEN r.cutoff IS NULL THEN 'UNKNOWN_DEADLINE'
            WHEN COALESCE(e.lanes,0)=6 AND COALESCE(o.tickets,0)=120 THEN 'BOTH_PRESENT'
            WHEN COALESCE(e.lanes,0)=6 THEN 'ODDS_INCOMPLETE'
            WHEN COALESCE(o.tickets,0)=120 THEN 'EXHIBITION_INCOMPLETE'
            ELSE 'BOTH_INCOMPLETE' END AS snapshot_status
FROM target r
LEFT JOIN LATERAL (
 SELECT MAX(q.lane_count) AS lanes, COUNT(*) AS labels
 FROM (
   SELECT e.snapshot_label, COUNT(DISTINCT e.lane) AS lane_count
   FROM public.v2_realtime_exhibition_snapshots e
   WHERE e.race_id=r.race_id
     AND r.cutoff IS NOT NULL
     AND e.snapshot_at < r.cutoff
     AND e.exhibition_time IS NOT NULL
   GROUP BY e.snapshot_label
 ) q
) e ON true
LEFT JOIN LATERAL (
 SELECT MAX(q.ticket_count) AS tickets, COUNT(*) AS labels
 FROM (
   SELECT o.snapshot_label, COUNT(DISTINCT o.ticket) AS ticket_count
   FROM public.v2_realtime_odds_snapshots o
   WHERE o.race_id=r.race_id
     AND r.cutoff IS NOT NULL
     AND o.snapshot_at < r.cutoff
     AND o.odds > 0
   GROUP BY o.snapshot_label
 ) q
) o ON true
ORDER BY r.race_id;
COMMIT;
SELECT 'V5_FORWARD_AFTER_READONLY_COMPLETE_NO_DB_WRITES' AS verdict;
