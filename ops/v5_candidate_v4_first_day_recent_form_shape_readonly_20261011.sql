-- V5 diagnostic ONLY: which recent_form JSON shapes exist on 2025-07-01?
-- Railway / production / postgres-hobby-fullhistory-candidate-v4 > Data > Query.
-- One SELECT, one summary row, Q1 = 144 distinct races prerequisite.
-- Indexed Q1 date and entries(race_id,lane), <= 864 expected slots; no Q3,
-- payout, exhibition, identifiable racer/race detail or raw JSON output.
-- Existing prior-day audit: 864 JSON containers but 0 history items.
-- Empty arrays may be an intentional warm-up state; DO NOT invent histories.
WITH races AS MATERIALIZED (
  SELECT race_id FROM public.v2_races
  WHERE race_date = DATE '2025-07-01'
),
q1 AS MATERIALIZED (
  SELECT count(*)::bigint n, count(race_id)::bigint nonnull,
         count(DISTINCT race_id)::bigint unique_ids FROM races
),
slots AS MATERIALIZED (
  SELECT r.race_id, x.lane
  FROM races r CROSS JOIN generate_series(1,6) AS x(lane)
  CROSS JOIN q1
  WHERE q1.n=144 AND q1.nonnull=144 AND q1.unique_ids=144
),
bounded AS MATERIALIZED (
  SELECT s.race_id, s.lane, e.race_id AS matched_entry,
         CASE WHEN pg_column_size(e.recent_form)<=12000
                 AND octet_length(e.recent_form::text)<=12000
              THEN e.recent_form ELSE NULL::jsonb END AS safe_form
  FROM slots s LEFT JOIN public.v2_race_entries e
    ON e.race_id=s.race_id AND e.lane=s.lane
),
shape AS MATERIALIZED (
  SELECT matched_entry, jsonb_typeof(safe_form) AS root_type,
         CASE WHEN jsonb_typeof(safe_form)='array'
              THEN jsonb_array_length(safe_form) END AS root_length,
         CASE WHEN jsonb_typeof(safe_form->'history')='array'
              THEN jsonb_array_length(safe_form->'history') END AS history_length,
         CASE WHEN jsonb_typeof(safe_form->'recent_form')='array'
              THEN jsonb_array_length(safe_form->'recent_form') END AS nested_recent_length,
         CASE WHEN jsonb_typeof(safe_form)='object'
              THEN safe_form='{}'::jsonb ELSE FALSE END AS empty_object,
         safe_form
  FROM bounded
),
summary AS (
  SELECT count(*)::bigint slots_seen,
         count(matched_entry)::bigint entries_seen,
         count(*) FILTER (WHERE safe_form IS NULL)::bigint null_or_over_12kb,
         count(*) FILTER (WHERE root_type='array')::bigint root_array,
         count(*) FILTER (WHERE root_type='array' AND root_length=0)::bigint empty_root_array,
         count(*) FILTER (WHERE root_type='array' AND root_length BETWEEN 1 AND 5)::bigint root_array_1_to_5,
         count(*) FILTER (WHERE root_type='array' AND root_length>5)::bigint root_array_over_5,
         count(*) FILTER (WHERE root_type='object')::bigint root_object,
         count(*) FILTER (WHERE empty_object)::bigint empty_root_object,
         count(*) FILTER (WHERE history_length=0)::bigint empty_nested_history_array,
         count(*) FILTER (WHERE history_length>0)::bigint nonempty_nested_history_array,
         count(*) FILTER (WHERE nested_recent_length=0)::bigint empty_nested_recent_array,
         count(*) FILTER (WHERE nested_recent_length>0)::bigint nonempty_nested_recent_array,
         count(*) FILTER (
           WHERE safe_form IS NOT NULL AND root_type NOT IN ('array','object')
         )::bigint other_json_types
  FROM shape
),
top_keys AS (
  SELECT coalesce(string_agg(key_name, ', ' ORDER BY key_name),'NONE') AS object_key_names
  FROM (
    SELECT DISTINCT left(j.key_name,48) AS key_name
    FROM shape s CROSS JOIN LATERAL jsonb_object_keys(
      CASE WHEN s.root_type='object' THEN s.safe_form ELSE '{}'::jsonb END
    ) AS j(key_name)
    ORDER BY 1 LIMIT 16
  ) keys
)
SELECT DATE '2025-07-01' AS race_date_checked, q1.n AS q1_races_rechecked,
       s.slots_seen, s.entries_seen, s.null_or_over_12kb,
       s.root_array, s.empty_root_array, s.root_array_1_to_5,
       s.root_array_over_5, s.root_object, s.empty_root_object,
       s.empty_nested_history_array, s.nonempty_nested_history_array,
       s.empty_nested_recent_array, s.nonempty_nested_recent_array,
       s.other_json_types, k.object_key_names,
       CASE
         WHEN q1.n<>144 OR q1.nonnull<>144 OR q1.unique_ids<>144
           THEN 'HOLD_Q1_CHANGED'
         WHEN s.slots_seen<>864 OR s.entries_seen<>864
           THEN 'HOLD_ENTRY_POPULATION'
         WHEN s.null_or_over_12kb>0
           THEN 'HOLD_NULL_OR_OVERSIZE_FORM'
         WHEN s.empty_root_array=864
           THEN 'ALL_EMPTY_ARRAYS_CHECK_WARMUP_SOURCE'
         WHEN s.empty_root_object=864
           THEN 'ALL_EMPTY_OBJECTS_CHECK_UPSTREAM_SOURCE'
         ELSE 'MIXED_OR_ALTERNATE_JSON_STRUCTURE_REVIEW'
       END AS form_shape_verdict,
       'DIAG_ONLY_NO_REPAIR_Q3_ROI_FORWARD_OR_BUY'::text AS authorization
FROM q1 CROSS JOIN summary s CROSS JOIN top_keys k;
