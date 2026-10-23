-- V5 strong-core: exact per-racer previous-day five finish records.
-- ONE REAL race; READ-ONLY; no backfill, snapshot rewriting, training, or BUY.
-- The earlier six-lane audit showed top3_pct, but the native research helper
-- needs tuple[{"race_date": ..., "finish_position": ...}, ...] per lane.
-- K records fetched before race-day midnight are NOT an independently frozen
-- predecision receipt. HOLD first-capture, prior-day factor state, and BUY.
-- Run on ConoHa local PostgreSQL:
--  sudo -u postgres psql -d railway -X -v ON_ERROR_STOP=1 \
--    -v race_id=20261023_21_02 -f /tmp/v5_prior_day_recent_form.sql
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

WITH target AS MATERIALIZED (
  SELECT race_id,race_date,deadline_at
  FROM boat_data.races
  WHERE race_id=:'race_id'
    AND race_date >= DATE '2025-07-01'
), entrants AS MATERIALIZED (
  SELECT e.lane,e.racer_number,e.racer_class
  FROM boat_data.entries e
  JOIN target r ON r.race_id=e.race_id
  WHERE e.lane BETWEEN 1 AND 6
), history AS (
 SELECT e.lane,e.racer_number,e.racer_class,
        k.n AS prior_valid_rows,
        k.form AS recent_form_5,
        k.newest_history_day,
        k.latest_fetch_at
 FROM entrants e
 CROSS JOIN target t
 LEFT JOIN LATERAL (
   SELECT count(*)::integer AS n,
          COALESCE(jsonb_agg(
            jsonb_build_object('race_date',p.race_date,
                               'finish_position',p.finish_position)
            ORDER BY p.race_date DESC,p.deadline_at DESC NULLS LAST,
                     p.race_no DESC,p.race_id DESC,p.lane DESC
          ),'[]'::jsonb) AS form,
          max(p.race_date) AS newest_history_day,
          max(p.fetched_at) AS latest_fetch_at
   FROM (
     SELECT r.race_date,r.deadline_at,r.race_no,
            h.race_id,h.lane,h.finish_position,h.fetched_at
     FROM public.v2_result_entries h
     JOIN public.v2_races r ON r.race_id=h.race_id
     WHERE h.racer_number=e.racer_number
       AND h.source='official_k_file'
       AND r.race_date>=DATE '2025-07-01'
       AND r.race_date<t.race_date
       AND h.fetched_at IS NOT NULL
       AND h.fetched_at < (t.race_date::timestamp AT TIME ZONE 'Asia/Tokyo')
       AND h.finish_position BETWEEN 1 AND 6
       AND h.is_flying IS NOT TRUE
       AND h.is_late IS NOT TRUE
     ORDER BY r.race_date DESC,r.deadline_at DESC NULLS LAST,
              r.race_no DESC,h.race_id DESC,h.lane DESC
     LIMIT 5
   ) p
 ) k ON true
)
SELECT lane,racer_number,racer_class,prior_valid_rows,
       newest_history_day,
       to_char(latest_fetch_at AT TIME ZONE 'Asia/Tokyo',
               'YYYY-MM-DD HH24:MI:SS') AS latest_fetch_jst,
       recent_form_5,
       CASE
         WHEN (SELECT count(*) FROM entrants)<>6
           OR (SELECT count(DISTINCT racer_number) FROM entrants)<>6
           THEN 'HOLD_SIX_ACTUAL_LANES_NOT_PROVED'
         WHEN prior_valid_rows<>5 THEN 'HOLD_FIVE_PRIOR_RACES_MISSING'
         ELSE 'HOLD_NO_FROZEN_PRIOR_COUNTERS_OR_FIRST_CAPTURE'
       END AS research_gate
FROM history
ORDER BY lane;

COMMIT;
SELECT 'V5_K_PRIOR_5_PAYLOAD_READONLY_NO_MODEL_NO_BUY' AS audit;
