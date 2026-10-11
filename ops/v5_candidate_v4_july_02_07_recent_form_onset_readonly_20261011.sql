-- V5 July-2025 recent_form WARM-UP CHECKPOINTS, read-only metadata aggregate.
-- Railway: boat-v2-postgres / production / postgres-hobby-fullhistory-candidate-v4 / Data > Query.
-- Six consecutive days ONLY: 2025-07-02 through 2025-07-07 (July 1 verified empty).
-- Date-indexed v2_races and race_id+lane-indexed v2_race_entries; no entire-month scan.
-- At most six days x 400 races x six slots, no result/odds/exhibition reads.
-- Counts only: no race IDs, racer numbers, histories, raw JSON, or DB writes.
-- First nonempty history in this DB does NOT establish the earliest official data date or real-time capture.
WITH sample_days(day) AS (
  VALUES (DATE '2025-07-02'), (DATE '2025-07-03'),
         (DATE '2025-07-04'), (DATE '2025-07-05'),
         (DATE '2025-07-06'), (DATE '2025-07-07')
),
race_base AS MATERIALIZED (
  SELECT r.race_date, r.race_id
  FROM public.v2_races r
  WHERE r.race_date IN (DATE '2025-07-02', DATE '2025-07-03',
                        DATE '2025-07-04', DATE '2025-07-05',
                        DATE '2025-07-06', DATE '2025-07-07')
),
q1 AS MATERIALIZED (
  SELECT d.day, count(r.race_id)::bigint race_rows,
         count(DISTINCT r.race_id)::bigint unique_race_ids
  FROM sample_days d
  LEFT JOIN race_base r ON r.race_date=d.day
  GROUP BY d.day
),
slots AS MATERIALIZED (
  SELECT r.race_date, r.race_id, n.lane
  FROM race_base r
  JOIN q1 q ON q.day=r.race_date
  CROSS JOIN generate_series(1,6) AS n(lane)
  WHERE q.race_rows BETWEEN 1 AND 400
    AND q.unique_race_ids=q.race_rows
),
forms AS MATERIALIZED (
  SELECT s.race_date, e.race_id AS matched_entry,
         CASE WHEN pg_column_size(e.recent_form)<=12000
                 AND octet_length(e.recent_form::text)<=12000
              THEN e.recent_form ELSE NULL::jsonb END AS safe_form
  FROM slots s
  LEFT JOIN public.v2_race_entries e
    ON e.race_id=s.race_id AND e.lane=s.lane
),
parsed AS (
  SELECT race_date, matched_entry, safe_form,
         CASE
           WHEN jsonb_typeof(safe_form)='array' THEN safe_form
           WHEN jsonb_typeof(safe_form->'history')='array' THEN safe_form->'history'
           WHEN jsonb_typeof(safe_form->'recent_form')='array' THEN safe_form->'recent_form'
           ELSE NULL::jsonb END AS form_array
  FROM forms
),
aggregate AS (
  SELECT race_date, count(*)::bigint slot_rows,
         count(matched_entry)::bigint entry_rows,
         count(*) FILTER (WHERE safe_form IS NULL)::bigint missing_or_large_json_rows,
         count(*) FILTER (WHERE jsonb_typeof(form_array)='array'
                            AND jsonb_array_length(form_array)=0)::bigint empty_history_arrays,
         count(*) FILTER (WHERE jsonb_typeof(form_array)='array'
                            AND jsonb_array_length(form_array) BETWEEN 1 AND 5)::bigint one_to_five_history_arrays,
         count(*) FILTER (WHERE jsonb_typeof(form_array)='array'
                            AND jsonb_array_length(form_array)>5)::bigint over_five_history_arrays,
         count(*) FILTER (WHERE form_array IS NULL)::bigint unrecognized_shape_rows
  FROM parsed GROUP BY race_date
)
SELECT q.day AS race_date_checked, q.race_rows AS q1_race_rows,
       q.unique_race_ids, coalesce(a.slot_rows,0)::bigint AS lane_slots,
       coalesce(a.entry_rows,0)::bigint AS entry_rows,
       coalesce(a.missing_or_large_json_rows,0)::bigint AS missing_or_large_json_rows,
       coalesce(a.empty_history_arrays,0)::bigint AS empty_history_arrays,
       coalesce(a.one_to_five_history_arrays,0)::bigint AS one_to_five_history_arrays,
       coalesce(a.over_five_history_arrays,0)::bigint AS over_five_history_arrays,
       coalesce(a.unrecognized_shape_rows,0)::bigint AS unrecognized_shape_rows,
       CASE
         WHEN q.race_rows=0 THEN 'HOLD_ZERO_RACES_NOT_HOLIDAY_PROOF'
         WHEN q.race_rows>400 OR q.unique_race_ids<>q.race_rows THEN 'HOLD_Q1_OUT_OF_CAP_OR_DUPLICATE'
         WHEN coalesce(a.slot_rows,0)<>q.race_rows*6 OR coalesce(a.entry_rows,0)<>q.race_rows*6
           THEN 'HOLD_MISSING_OR_DUPLICATE_ENTRIES'
         WHEN coalesce(a.missing_or_large_json_rows,0)>0 OR coalesce(a.over_five_history_arrays,0)>0
             OR coalesce(a.unrecognized_shape_rows,0)>0 THEN 'HOLD_JSON_CONTENT_OR_SHAPE'
         WHEN coalesce(a.one_to_five_history_arrays,0)=0 THEN 'NO_HISTORY_ON_THIS_DATE'
         ELSE 'SOME_PRIOR_HISTORY_PRESENT_REVIEW_COVERAGE'
       END AS checkpoint_verdict,
       'SAMPLES_ONLY_NO_Q3_ROI_FORWARD_OR_BUY'::text AS authorization
FROM q1 q LEFT JOIN aggregate a ON a.race_date=q.day
ORDER BY q.day;
