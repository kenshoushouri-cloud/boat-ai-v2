-- Inspect when the 5 odds-gap races and Edogawa 3R were observed.
-- Read-only; historical metadata is not proof of official publish time.
-- Avoid changing data, timers, collectors, or purchasing state.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout = '12000ms';
SET LOCAL lock_timeout = '1500ms';

WITH requested(race_id) AS (
 VALUES ('20261022_03_03'), -- Edogawa exhibition time 0
        ('20261022_05_01'), -- observed but no 3T odds
        ('20261022_05_11'),
        ('20261022_11_04'),
        ('20261022_14_04'),
        ('20261022_14_11')
), races AS (
 SELECT q.race_id, r.deadline_at::timestamptz AS cutoff
 FROM requested q
 LEFT JOIN public.v2_races r ON r.race_id=q.race_id
)
SELECT 'V5_MISSING_TIMING' AS audit,
       r.race_id,
       to_char(r.cutoff AT TIME ZONE 'Asia/Tokyo','MM-DD HH24:MI') AS cutoff_jst,
       COALESCE(w.pre_count,0) AS weather_before,
       to_char(w.first_at AT TIME ZONE 'Asia/Tokyo','HH24:MI:SS') AS first_weather_jst,
       to_char(w.last_at AT TIME ZONE 'Asia/Tokyo','HH24:MI:SS') AS last_weather_jst,
       CASE WHEN w.last_at IS NULL OR r.cutoff IS NULL THEN NULL
            ELSE ROUND(EXTRACT(EPOCH FROM (r.cutoff-w.last_at))/60.0,1)
       END AS last_weather_lead_min,
       COALESCE(e.best_lanes,0) AS max_exh_lanes,
       COALESCE(o.best_tickets,0) AS max_odds_tickets,
       COALESCE(o.fallback_rows,0) AS odds_fallback_rows
FROM races r
LEFT JOIN LATERAL (
  SELECT count(*) AS pre_count, min(snapshot_at) AS first_at,
         max(snapshot_at) AS last_at
  FROM public.v2_realtime_weather_snapshots w
  WHERE w.race_id=r.race_id AND r.cutoff IS NOT NULL
    AND w.snapshot_at < r.cutoff
) w ON TRUE
LEFT JOIN LATERAL (
  SELECT max(lanes) AS best_lanes FROM (
     SELECT e.snapshot_label, count(DISTINCT e.lane) AS lanes
     FROM public.v2_realtime_exhibition_snapshots e
     WHERE e.race_id=r.race_id AND r.cutoff IS NOT NULL
       AND e.snapshot_at<r.cutoff AND e.exhibition_time IS NOT NULL
     GROUP BY e.snapshot_label
  ) labels
) e ON TRUE
LEFT JOIN LATERAL (
  SELECT max(tickets) AS best_tickets, sum(fallback_count) AS fallback_rows
  FROM (
     SELECT o.snapshot_label,
            count(DISTINCT o.ticket) FILTER (WHERE o.odds>0) AS tickets,
            count(*) FILTER (WHERE o.source='v2_odds_trifecta_fallback') AS fallback_count
     FROM public.v2_realtime_odds_snapshots o
     WHERE o.race_id=r.race_id AND r.cutoff IS NOT NULL
       AND o.snapshot_at < r.cutoff
     GROUP BY o.snapshot_label
  ) labels
) o ON TRUE
ORDER BY r.race_id;
COMMIT;
SELECT 'V5_MISSING_TIMING_READONLY_COMPLETE_NO_DB_WRITES' AS verdict;
