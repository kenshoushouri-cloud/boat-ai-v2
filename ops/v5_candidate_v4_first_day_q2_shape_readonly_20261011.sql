-- V5 first-day Q2 SHAPE smoke: one read-only SELECT, one output row.
-- Railway / production / postgres-hobby-fullhistory-candidate-v4 / Data > Query ONLY.
-- DATE: 2025-07-01. Q1 observed 144 distinct rows (user-supplied 2026-10-11).
-- Halt downstream joins if the Q1 count or unique count has changed.
-- Only 144 x six nominal slots; joins use preflight-checked (race_id,lane)
-- and (race_id,snapshot_label,lane) B-tree index prefixes.
-- Does not return race IDs, raw JSON, full histories or Q3/result/payout.
-- No LIMIT, DISTINCT-on-picking, table mutation, or buying/ROI authorization.
-- Historical exhibition snapshot rows do not prove original predeadline capture.
WITH races AS MATERIALIZED (
  SELECT race_id, deadline_at
  FROM public.v2_races
  WHERE race_date = DATE '2025-07-01'
),
q1 AS MATERIALIZED (
  SELECT count(*)::bigint AS race_rows,
         count(DISTINCT race_id)::bigint AS unique_ids,
         count(race_id)::bigint AS nonnull_ids
  FROM races
),
slots AS MATERIALIZED (
  SELECT r.race_id, r.deadline_at, k.lane
  FROM races r CROSS JOIN generate_series(1,6) AS k(lane)
  CROSS JOIN q1
  WHERE q1.race_rows = 144
    AND q1.unique_ids = 144
    AND q1.nonnull_ids = 144
),
entry_per_slot AS (
  SELECT s.race_id, s.lane,
         count(e.race_id)::bigint AS matched,
         count(e.racer_number)::bigint AS racer_number_nonnull,
         count(*) FILTER (
           WHERE e.racer_class_text IN ('A1','A2','B1','B2')
         )::bigint AS valid_text_class,
         count(*) FILTER (
           WHERE jsonb_typeof(e.recent_form) IN ('array','object')
         )::bigint AS recent_json_container
  FROM slots s
  LEFT JOIN public.v2_race_entries e
    ON e.race_id=s.race_id AND e.lane=s.lane
  GROUP BY s.race_id, s.lane
),
exhibition_per_slot AS (
  SELECT s.race_id, s.lane,
         count(x.race_id)::bigint AS matched,
         count(*) FILTER (
           WHERE x.exhibition_time_rank BETWEEN 1 AND 6
         )::bigint AS rank_present,
         count(*) FILTER (
           WHERE x.snapshot_at > s.deadline_at
         )::bigint AS post_deadline_snapshot
  FROM slots s
  LEFT JOIN public.v2_realtime_exhibition_snapshots x
    ON x.race_id=s.race_id AND x.snapshot_label='historical'
   AND x.lane=s.lane
  GROUP BY s.race_id, s.lane
),
entry_totals AS (
  SELECT count(*)::bigint AS slots,
         coalesce(sum(matched),0)::bigint AS rows_found,
         count(*) FILTER (WHERE matched=0)::bigint AS missing_slots,
         count(*) FILTER (WHERE matched>1)::bigint AS duplicate_slots,
         coalesce(sum(racer_number_nonnull),0)::bigint AS numbered_rows,
         coalesce(sum(valid_text_class),0)::bigint AS valid_grade_rows,
         coalesce(sum(recent_json_container),0)::bigint AS recent_json_rows
  FROM entry_per_slot
),
exhibition_totals AS (
  SELECT coalesce(sum(matched),0)::bigint AS rows_found,
         count(*) FILTER (WHERE matched=0)::bigint AS missing_slots,
         count(*) FILTER (WHERE matched>1)::bigint AS duplicate_slots,
         coalesce(sum(rank_present),0)::bigint AS rank_rows,
         coalesce(sum(post_deadline_snapshot),0)::bigint AS after_deadline_rows
  FROM exhibition_per_slot
)
SELECT DATE '2025-07-01' AS race_date_checked,
       q1.race_rows AS q1_rows_rechecked,
       e.slots AS expected_lane_slots,
       e.rows_found AS entry_rows,
       e.missing_slots AS missing_entry_slots,
       e.duplicate_slots AS duplicate_entry_slots,
       e.numbered_rows AS racer_number_rows,
       e.valid_grade_rows AS valid_text_grade_rows,
       e.recent_json_rows AS recent_form_container_rows,
       x.rows_found AS historical_exhibition_rows,
       x.missing_slots AS missing_historical_exhibition_slots,
       x.duplicate_slots AS duplicate_historical_exhibition_slots,
       x.rank_rows AS exhibition_rank_rows,
       x.after_deadline_rows AS post_deadline_exhibition_rows,
       CASE
         WHEN q1.race_rows<>144 OR q1.unique_ids<>144 OR q1.nonnull_ids<>144
           THEN 'HOLD_Q1_INVENTORY_CHANGED'
         WHEN e.slots<>864 OR e.missing_slots<>0 OR e.duplicate_slots<>0
           OR e.rows_found<>864
           THEN 'HOLD_Q2_ENTRY_POPULATION'
         WHEN e.numbered_rows<>864 OR e.valid_grade_rows<>864
           OR e.recent_json_rows<>864
           THEN 'HOLD_Q2_ENTRY_FIELDS'
         WHEN x.missing_slots<>0 OR x.duplicate_slots<>0
           OR x.rows_found<>864 OR x.rank_rows<>864
           THEN 'HOLD_Q2_HISTORICAL_EXHIBITION'
         ELSE 'Q2_SHAPE_COUNTS_ONLY_NOT_ASOF_VERIFIED'
       END AS q2_verdict,
       'NO_Q3_ROI_FORWARD_OR_BUY_AUTHORIZATION'::text AS next_action_authorization
FROM q1 CROSS JOIN entry_totals e CROSS JOIN exhibition_totals x;
