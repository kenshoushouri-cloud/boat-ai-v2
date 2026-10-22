-- Actual (not synthetic) V5 candidate readiness from 13 shared READ ONLY views.
-- This does NOT generate a forecast, scores, stakes or any BUY authorization.
-- Only inspect up to 6 upcoming races on today's JST date; avoid backfills.
-- Timing/counts are structural indications, not original immutable evidence.
\set ON_ERROR_STOP on
\pset pager off
BEGIN TRANSACTION READ ONLY;
SET LOCAL lock_timeout = '1000ms';
SET LOCAL statement_timeout = '12000ms';
SET LOCAL search_path = pg_catalog, public;

WITH upcoming AS MATERIALIZED (
 SELECT race_id, race_date, deadline_at::timestamptz AS cutoff
 FROM boat_data.races
 WHERE race_date = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Tokyo')::date
   AND deadline_at IS NOT NULL
   AND deadline_at::timestamptz > CURRENT_TIMESTAMP
 ORDER BY deadline_at::timestamptz, race_id
 LIMIT 6
)
SELECT 'V5_LIVE_INPUT_SAMPLE_NO_SCORING' AS audit, r.race_id,
  to_char(r.cutoff AT TIME ZONE 'Asia/Tokyo','HH24:MI') AS cutoff_jst,
  COALESCE(e.all_rows,0) AS entry_rows,
  COALESCE(e.lanes,0) AS distinct_lanes,
  COALESCE(e.ids_present,0) AS racer_ids,
  COALESCE(e.class_present,0) AS racer_classes,
  COALESCE(e.motor_present,0) AS motor_keys,
  COALESCE(e.boat_present,0) AS boat_keys,
  COALESCE(e.recent_form_arrays,0) AS recent_form_array_shapes,
  COALESCE(x.lanes,0) AS same_label_predeadline_exhibition_lanes,
  COALESCE(o.tickets,0) AS same_label_predeadline_positive_odds,
  CASE
   WHEN COALESCE(e.all_rows,0)<>6 OR COALESCE(e.lanes,0)<>6
     THEN 'HOLD_ENTRY_NOT_SIX'
   WHEN COALESCE(e.ids_present,0)<>6 OR COALESCE(e.class_present,0)<>6
     THEN 'HOLD_RACER_ID_OR_CLASS'
   WHEN COALESCE(e.motor_present,0)<>6 OR COALESCE(e.boat_present,0)<>6
     THEN 'HOLD_MOTOR_OR_BOAT'
   WHEN COALESCE(e.recent_form_arrays,0)<>6
     THEN 'HOLD_RECENT_FORM_SHAPE'
   WHEN COALESCE(x.lanes,0)<6 OR COALESCE(o.tickets,0)<120
     THEN 'HOLD_SNAPSHOT_INCOMPLETE'
   ELSE 'STRUCTURAL_ONLY_NO_ASOF_PROOF_NO_MODEL'
  END AS verdict
FROM upcoming r
LEFT JOIN LATERAL (
 SELECT count(*)::int AS all_rows,
    count(DISTINCT lane) FILTER(WHERE lane BETWEEN 1 AND 6)::int AS lanes,
    count(*) FILTER(WHERE lane BETWEEN 1 AND 6 AND racer_number IS NOT NULL)::int AS ids_present,
    count(*) FILTER(WHERE lane BETWEEN 1 AND 6 AND racer_class IS NOT NULL)::int AS class_present,
    count(*) FILTER(WHERE lane BETWEEN 1 AND 6 AND motor_no IS NOT NULL)::int AS motor_present,
    count(*) FILTER(WHERE lane BETWEEN 1 AND 6 AND boat_no IS NOT NULL)::int AS boat_present,
    count(*) FILTER(WHERE lane BETWEEN 1 AND 6 AND jsonb_typeof(recent_form)='array')::int AS recent_form_arrays
 FROM boat_data.entries WHERE race_id=r.race_id
) e ON true
LEFT JOIN LATERAL (
 SELECT coalesce(max(lanes),0)::int AS lanes FROM (
   SELECT snapshot_label, count(DISTINCT lane)::int AS lanes
   FROM boat_data.exhibition_snapshots
   WHERE race_id=r.race_id
     AND lane BETWEEN 1 AND 6
     AND exhibition_time IS NOT NULL
     AND snapshot_at < r.cutoff AND snapshot_at < CURRENT_TIMESTAMP
   GROUP BY snapshot_label
 ) x
) x ON true
LEFT JOIN LATERAL (
 SELECT coalesce(max(tickets),0)::int AS tickets FROM (
   SELECT snapshot_label, count(DISTINCT ticket)::int AS tickets
   FROM boat_data.odds_snapshots
   WHERE race_id=r.race_id AND odds > 0
     AND snapshot_at < r.cutoff AND snapshot_at < CURRENT_TIMESTAMP
   GROUP BY snapshot_label
 ) o
) o ON true
ORDER BY r.cutoff, r.race_id;

COMMIT;
SELECT 'V5_LIVE_INPUT_SAMPLE_READONLY_DONE_NO_FORECAST_NO_BUY' AS audit;
