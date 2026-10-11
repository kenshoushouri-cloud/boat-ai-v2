-- V5 archived RESEARCH data, bounded to ONE period <= 7 completed JST days.
-- SQL TEMPLATE for psycopg named parameters, NOT psql-ready:
--   %(start_date)s      inclusive ISO date >= 2025-07-01
--   %(end_exclusive)s   exclusive ISO date; 1..7 days after start
-- DO NOT execute on Railway without a separate schema/index/cost preflight.
-- Read-only transaction, role, statement_timeout, row/network-size budget required.
-- Run each SELECT SEPARATELY, in order: INVENTORY, LANES, RESULTS.
-- NEVER merge results/payout into prediction features or drop missing inventory.
-- No DISTINCT, LIMIT, OR one-row-picking: duplicates must remain visible and HOLD.
-- Even results labelled 'official' in DB lack independent refund authentication.
-- This file makes NO claims about six positive active starts or first observation.

-- Q1: exact claimed inventory (no outcome-based filters).
WITH p AS (
    SELECT %(start_date)s::date AS start_day,
           %(end_exclusive)s::date AS end_day
),
bounded AS (
    SELECT * FROM p
    WHERE start_day >= DATE '2025-07-01'
      AND (end_day - start_day) BETWEEN 1 AND 7
      AND end_day <= (now() AT TIME ZONE 'Asia/Tokyo')::date
)
SELECT r.race_id, r.race_date, r.deadline_at
FROM bounded b
JOIN public.v2_races r
  ON r.race_date >= b.start_day
 AND r.race_date < b.end_day
ORDER BY r.race_date, r.race_id;

-- Q2: 6 raw lane candidate rows PER inventoried race. This is NOT
-- predecision proof. LEFT JOIN preserves missing lanes as explicit NULLs.
-- If historical snapshots/entries duplicate: all rows remain -> offline HOLD.
WITH p AS (
    SELECT %(start_date)s::date AS start_day,
           %(end_exclusive)s::date AS end_day
),
bounded AS (
    SELECT * FROM p
    WHERE start_day >= DATE '2025-07-01'
      AND (end_day - start_day) BETWEEN 1 AND 7
      AND end_day <= (now() AT TIME ZONE 'Asia/Tokyo')::date
),
inventory AS MATERIALIZED (
    SELECT r.race_id, r.race_date, r.deadline_at
    FROM bounded b
    JOIN public.v2_races r
      ON r.race_date >= b.start_day AND r.race_date < b.end_day
)
SELECT r.race_id, r.race_date, r.deadline_at, lanes.lane,
       e.racer_number,
       CASE WHEN e.racer_class_text IN ('A1','A2','B1','B2')
            THEN e.racer_class_text ELSE NULL::text END AS racer_class,
       jsonb_typeof(e.recent_form) AS recent_form_json_type,
       CASE
         WHEN jsonb_typeof(e.recent_form) = 'array'
           THEN e.recent_form
         WHEN jsonb_typeof(e.recent_form->'history') = 'array'
           THEN e.recent_form->'history'
         WHEN jsonb_typeof(e.recent_form->'recent_form') = 'array'
           THEN e.recent_form->'recent_form'
         ELSE NULL::jsonb
       END AS parsed_history,
       x.source AS exhibition_source,
       x.exhibition_time_rank,
       x.snapshot_at AS exhibition_snapshot_at,
       x.raw->>'reuse_contract' AS exhibition_reuse_contract,
       x.raw->>'source_contract' AS exhibition_source_contract,
       x.raw->>'source_snapshot_label' AS source_snapshot_label,
       x.raw->>'source_snapshot_at' AS source_snapshot_at_text,
       FALSE AS independent_official_six_active_verified,
       FALSE AS original_first_observation_verified,
       FALSE AS forward_eligible,
       FALSE AS buy_eligible
FROM inventory r
CROSS JOIN generate_series(1, 6) AS lanes(lane)
LEFT JOIN public.v2_race_entries e
  ON e.race_id = r.race_id AND e.lane = lanes.lane
LEFT JOIN public.v2_realtime_exhibition_snapshots x
  ON x.race_id = r.race_id AND x.lane = lanes.lane
 AND x.snapshot_label = 'historical'
ORDER BY r.race_date, r.race_id, lanes.lane,
         e.racer_number, x.snapshot_at;

-- Q3: strictly postrace data stream, NEVER available to predictor.
-- Missing result remains one row per inventoried race with NULL fields.
-- Duplicate result rows are NOT masked; offline ingestion MUST reject them.
-- No source-verified refund mapping exists in this extraction: NULL != ().
WITH p AS (
    SELECT %(start_date)s::date AS start_day,
           %(end_exclusive)s::date AS end_day
),
bounded AS (
    SELECT * FROM p
    WHERE start_day >= DATE '2025-07-01'
      AND (end_day - start_day) BETWEEN 1 AND 7
      AND end_day <= (now() AT TIME ZONE 'Asia/Tokyo')::date
),
inventory AS MATERIALIZED (
    SELECT r.race_id, r.race_date
    FROM bounded b
    JOIN public.v2_races r
      ON r.race_date >= b.start_day AND r.race_date < b.end_day
)
SELECT r.race_id, r.race_date,
       rs.result_status, rs.race_status,
       rs.trifecta_ticket AS winning_ticket,
       rs.trifecta_payout_yen AS payout_per_100_yen,
       NULL::integer[] AS refund_boats,
       FALSE AS refund_section_verified,
       FALSE AS whole_race_void_verified,
       FALSE AS v5_real_roi_verified,
       FALSE AS buy_eligible
FROM inventory r
LEFT JOIN public.v2_results rs ON rs.race_id = r.race_id
ORDER BY r.race_date, r.race_id;
