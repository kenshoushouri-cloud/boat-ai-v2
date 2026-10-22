-- Historical 2026-10-22 odds coverage: read-only evidence, not proof of live buy-readiness.
-- Per race evaluate best predeadline snapshot_label, fallback, and presence of collection.
-- No write, no DDL, no official site refetch, and bounded to one racing date.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout = '20000ms';
SET LOCAL lock_timeout = '1500ms';

WITH races AS MATERIALIZED (
 SELECT race_id, deadline_at::timestamptz AS cutoff
 FROM public.v2_races
 WHERE race_date=DATE '2026-10-22'
), audit AS MATERIALIZED (
 SELECT r.race_id, r.cutoff,
        COALESCE(w.weather_rows,0) AS weather_rows,
        COALESCE(e.best_lanes,0) AS best_exhibition_lanes,
        COALESCE(o.best_tickets,0) AS best_positive_odds_tickets,
        COALESCE(o.odds_labels,0) AS odds_labels,
        COALESCE(o.fallback_rows,0) AS fallback_rows,
        CASE WHEN o.latest_snapshot IS NULL THEN NULL
             ELSE FLOOR(EXTRACT(EPOCH FROM (r.cutoff-o.latest_snapshot))/60)::integer
        END AS minutes_before_cutoff
 FROM races r
 LEFT JOIN LATERAL (
    SELECT COUNT(*) AS weather_rows
    FROM public.v2_realtime_weather_snapshots w
    WHERE w.race_id=r.race_id AND r.cutoff IS NOT NULL
      AND w.snapshot_at<r.cutoff
 ) w ON TRUE
 LEFT JOIN LATERAL (
    SELECT MAX(lanes) AS best_lanes
    FROM (
      SELECT e.snapshot_label,COUNT(DISTINCT e.lane) AS lanes
      FROM public.v2_realtime_exhibition_snapshots e
      WHERE e.race_id=r.race_id AND r.cutoff IS NOT NULL
        AND e.snapshot_at<r.cutoff AND e.exhibition_time IS NOT NULL
      GROUP BY e.snapshot_label
    ) labels
 ) e ON TRUE
 LEFT JOIN LATERAL (
    SELECT MAX(tickets) AS best_tickets,COUNT(*) AS odds_labels,
           SUM(fallback_count) AS fallback_rows,
           MAX(last_seen) AS latest_snapshot
    FROM (
      SELECT o.snapshot_label,
             COUNT(DISTINCT o.ticket) FILTER (WHERE o.odds>0) AS tickets,
             COUNT(*) FILTER (WHERE o.source='v2_odds_trifecta_fallback') AS fallback_count,
             MAX(o.snapshot_at) AS last_seen
      FROM public.v2_realtime_odds_snapshots o
      WHERE o.race_id=r.race_id AND r.cutoff IS NOT NULL
        AND o.snapshot_at<r.cutoff
      GROUP BY o.snapshot_label
    ) labels
 ) o ON TRUE
), in_scope AS (
 SELECT a.*,
        (a.weather_rows>0 OR a.best_exhibition_lanes>0 OR a.odds_labels>0)
         AS had_any_predeadline_snapshot
 FROM audit a
), report AS (
 SELECT 0 AS sort,
        'SUMMARY' AS category,
        COUNT(*)::text AS race_id_or_count,
        ('observed='||COUNT(*) FILTER (WHERE had_any_predeadline_snapshot)
         ||'; odds120='||COUNT(*) FILTER (WHERE had_any_predeadline_snapshot AND best_positive_odds_tickets=120)
         ||'; odds_partial='||COUNT(*) FILTER (WHERE had_any_predeadline_snapshot AND best_positive_odds_tickets BETWEEN 1 AND 119)
         ||'; odds_zero='||COUNT(*) FILTER (WHERE had_any_predeadline_snapshot AND best_positive_odds_tickets=0)
         ||'; fallback_races='||COUNT(*) FILTER (WHERE fallback_rows>0)) AS odds_information,
        ('exh6='||COUNT(*) FILTER (WHERE had_any_predeadline_snapshot AND best_exhibition_lanes=6)
          ||'; outside_observed='||COUNT(*) FILTER (WHERE NOT had_any_predeadline_snapshot)) AS other_information
 FROM in_scope
 UNION ALL
 SELECT 1 AS sort, 'ODDS_GAP' AS category, race_id AS race_id_or_count,
        ('best='||best_positive_odds_tickets||'/120'
         ||';labels='||odds_labels||';fallback_rows='||fallback_rows
         ||';last_minutes_to_cutoff='||COALESCE(minutes_before_cutoff::text,'UNKNOWN')) AS odds_information,
        ('exh_lanes='||best_exhibition_lanes||';weather_rows='||weather_rows) AS other_information
 FROM (
   SELECT * FROM in_scope
   WHERE had_any_predeadline_snapshot AND best_positive_odds_tickets<120
   ORDER BY race_id LIMIT 30
 ) gaps
 UNION ALL
 SELECT 2 AS sort, 'FALLBACK_SAMPLE' AS category, race_id,
        ('best='||best_positive_odds_tickets||'/120'
         ||';fallback_rows='||fallback_rows
         ||';last_minutes_to_cutoff='||COALESCE(minutes_before_cutoff::text,'UNKNOWN')),
        ('exh_lanes='||best_exhibition_lanes||';weather_rows='||weather_rows)
 FROM (
   SELECT * FROM in_scope WHERE fallback_rows>0 ORDER BY race_id LIMIT 10
 ) fallback
)
SELECT category,race_id_or_count,odds_information,other_information
FROM report
ORDER BY sort,race_id_or_count;

COMMIT;
SELECT 'V5_ODDS_COVERAGE_READONLY_COMPLETE_NO_DB_WRITES' AS verdict;
