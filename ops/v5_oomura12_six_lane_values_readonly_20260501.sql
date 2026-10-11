-- V5 archived-factor review: exactly ONE race, SIX candidate lanes, no writes.
-- NOT run on Railway. Query only after table/column/index and read-only role review.
-- Raw candidate lane values are retrospective; they are NOT official proof of
-- six active starters, original capture time, a frozen prediction, or BUY.
-- No payout, outcome, final odds, or cross-date scanning.
-- Important: DO NOT LIMIT or DISTINCT away duplicate lane/exhibition rows.
-- Count/validate all returned rows OFFLINE; any non-6 or duplicate => HOLD.
WITH one_race AS MATERIALIZED (
  SELECT race_id, race_date, deadline_at
    FROM public.v2_races
   WHERE race_id = '20260501_24_12'
),
six_lanes AS (
  SELECT generate_series(1, 6)::integer AS lane
)
SELECT r.race_id, r.race_date, r.deadline_at,
       l.lane,
       e.racer_number, e.racer_class,
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
  FROM one_race r
 CROSS JOIN six_lanes l
  LEFT JOIN public.v2_race_entries e
    ON e.race_id = r.race_id AND e.lane = l.lane
  LEFT JOIN public.v2_realtime_exhibition_snapshots x
    ON x.race_id = r.race_id AND x.lane = l.lane
   AND x.snapshot_label = 'historical'
 ORDER BY l.lane, e.racer_number, x.snapshot_at;
