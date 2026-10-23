-- V5 real-source six-lane input bridge (READ ONLY, one exact race).
-- The input is ACTUAL ConoHa boat_data VIEW data + prior official K history;
-- this is not model inference or a first-observation certificate.
-- 2026-10-23 confirmed source race: 20261023_21_02.
-- Usage:
--   sudo -u postgres psql -d railway -X -v ON_ERROR_STOP=1 \
--     -v race_id=20261023_21_02 -f /tmp/v5_live_six_lane_input_bridge.sql
-- No SQL writes. Do NOT enable BUY, routes, collector changes, or bulk copy.
-- IMPORTANT: the realtime sources are UPSERT-mutable, even when timestamped
-- before cutoff; archived as-of/first-write evidence is still UNVERIFIED.
\set ON_ERROR_STOP on
\pset pager off
\if :{?race_id}
\else
\set race_id 20261023_21_02
\endif
BEGIN TRANSACTION READ ONLY;
SET LOCAL lock_timeout='1000ms';
SET LOCAL statement_timeout='20000ms';
SET LOCAL work_mem='8MB';
SET LOCAL search_path=pg_catalog,public;

WITH target AS MATERIALIZED (
  SELECT race_id, race_date, deadline_at::timestamptz AS cutoff
  FROM boat_data.races
  WHERE race_id=:'race_id'
    AND deadline_at IS NOT NULL
), ex AS MATERIALIZED (
  SELECT x.snapshot_label,
         count(*)::int AS rows_n,
         count(DISTINCT lane) FILTER (
           WHERE lane BETWEEN 1 AND 6 AND exhibition_time IS NOT NULL
             AND exhibition_time_rank BETWEEN 1 AND 6
             AND x.snapshot_at < LEAST(t.cutoff,statement_timestamp())
         )::int AS six_lanes,
         count(DISTINCT exhibition_time_rank) FILTER (
           WHERE lane BETWEEN 1 AND 6 AND exhibition_time IS NOT NULL
             AND exhibition_time_rank BETWEEN 1 AND 6
             AND x.snapshot_at < LEAST(t.cutoff,statement_timestamp())
         )::int AS distinct_ranks,
         max(x.snapshot_at) AS last_at
  FROM boat_data.exhibition_snapshots x
  JOIN target t ON t.race_id=x.race_id
  WHERE x.snapshot_label IS NOT NULL
  GROUP BY x.snapshot_label
), od AS MATERIALIZED (
  SELECT o.snapshot_label,
         count(*)::int AS rows_n,
         count(DISTINCT ticket) FILTER (
           WHERE odds>0 AND ticket ~ '^[1-6]-[1-6]-[1-6]$'
             AND split_part(ticket,'-',1)<>split_part(ticket,'-',2)
             AND split_part(ticket,'-',1)<>split_part(ticket,'-',3)
             AND split_part(ticket,'-',2)<>split_part(ticket,'-',3)
             AND o.snapshot_at < LEAST(t.cutoff,statement_timestamp())
         )::int AS valid_tickets,
         max(o.snapshot_at) AS last_at
  FROM boat_data.odds_snapshots o
  JOIN target t ON t.race_id=o.race_id
  WHERE o.snapshot_label IS NOT NULL
  GROUP BY o.snapshot_label
), ent AS MATERIALIZED (
  SELECT s.snapshot_label,
         count(*)::int AS rows_n,
         count(DISTINCT lane) FILTER (
           WHERE lane BETWEEN 1 AND 6 AND racer_number IS NOT NULL
             AND s.snapshot_at < LEAST(t.cutoff,statement_timestamp())
         )::int AS valid_lanes,
         max(s.snapshot_at) AS last_at
  FROM boat_data.entry_snapshots s
  JOIN target t ON t.race_id=s.race_id
  WHERE s.snapshot_label IS NOT NULL
  GROUP BY s.snapshot_label
), chosen AS MATERIALIZED (
  SELECT x.snapshot_label, x.last_at AS exhibition_at,
         o.last_at AS odds_at, s.last_at AS entry_at,
         o.valid_tickets
  FROM ex x
  JOIN od o USING(snapshot_label)
  JOIN ent s USING(snapshot_label)
  WHERE x.rows_n=6 AND x.six_lanes=6 AND x.distinct_ranks=6
    AND o.rows_n=120 AND o.valid_tickets=120
    AND s.rows_n=6 AND s.valid_lanes=6
  ORDER BY greatest(x.last_at,o.last_at,s.last_at) DESC,x.snapshot_label DESC
  LIMIT 1
), core AS MATERIALIZED (
  SELECT e.race_id,e.lane,e.racer_number,e.racer_class,e.motor_no,e.boat_no
  FROM boat_data.entries e
  JOIN target t ON t.race_id=e.race_id
)
SELECT t.race_id,
       to_char(t.cutoff AT TIME ZONE 'Asia/Tokyo','HH24:MI') AS cutoff_jst,
       c.snapshot_label,
       count(*) OVER () AS core_rows,
       e.lane,e.racer_number,e.racer_class,e.motor_no,e.boat_no,
       x.exhibition_time_rank,
       coalesce(k.n,0) AS prior_k_5,
       coalesce(k.top3,0) AS prior_k_top3,
       CASE WHEN k.n>0 THEN round(100.0*k.top3/k.n,1)
            ELSE NULL END AS prior_k_top3_pct,
       c.valid_tickets AS odds_tickets,
       CASE WHEN c.snapshot_label IS NULL
              THEN 'HOLD_NO_COMPLETE_SAME_LABEL_ASOF_SNAPSHOT'
            WHEN e.racer_number IS NULL OR e.racer_class IS NULL
              OR e.motor_no IS NULL OR e.boat_no IS NULL
              THEN 'HOLD_CORE_FEATURES_MISSING'
            WHEN coalesce(k.n,0)<>5
              THEN 'HOLD_PRIOR_K_INCOMPLETE'
            ELSE 'HOLD_UNVERIFIED_FIRST_CAPTURE_AND_MODEL'
       END AS v5_gate
FROM target t
LEFT JOIN chosen c ON true
LEFT JOIN core e ON true
LEFT JOIN boat_data.exhibition_snapshots x
  ON x.race_id=e.race_id AND x.lane=e.lane
 AND x.snapshot_label=c.snapshot_label
 AND x.snapshot_at<LEAST(t.cutoff,statement_timestamp())
LEFT JOIN LATERAL (
  SELECT count(*)::int AS n,
         count(*) FILTER (WHERE finish_position<=3)::int AS top3
  FROM (
    SELECT h.finish_position
    FROM public.v2_result_entries h
    JOIN public.v2_races hr ON hr.race_id=h.race_id
    WHERE h.racer_number=e.racer_number
      AND h.source='official_k_file'
      AND hr.race_date>=DATE '2025-07-01'
      AND hr.race_date<t.race_date
      AND h.fetched_at<(t.race_date::timestamp AT TIME ZONE 'Asia/Tokyo')
      AND h.finish_position BETWEEN 1 AND 6
      AND h.is_flying IS NOT TRUE
      AND h.is_late IS NOT TRUE
    ORDER BY hr.race_date DESC,hr.deadline_at DESC NULLS LAST,
             hr.race_no DESC,h.race_id DESC,h.lane DESC
    LIMIT 5
  ) prior_rows
) k ON true
ORDER BY e.lane NULLS LAST;

COMMIT;
SELECT 'V5_REAL_SHARED_SIX_LANE_INPUT_READONLY_NO_INFERENCE_NO_BUY' AS audit;
