-- V5 research warm-up: prove stored recent_form item dates for 2025-07-02.
-- Railway Data > Query / boat-v2-postgres / production /
-- postgres-hobby-fullhistory-candidate-v4 ONLY. One aggregate SELECT.
-- 180 previously verified distinct races x six slots; B-tree indexes checked.
-- No history items/IDs or personal detail output; no result/odds/BUY/DDL.
-- A prior-day date proves chronology only, NOT original predeadline observation.
WITH races AS MATERIALIZED (
  SELECT race_id FROM public.v2_races
  WHERE race_date = DATE '2025-07-02'
),
q1 AS MATERIALIZED (
  SELECT count(*)::bigint race_rows,
         count(race_id)::bigint nonnull_ids,
         count(DISTINCT race_id)::bigint unique_ids
  FROM races
),
slots AS MATERIALIZED (
  SELECT r.race_id, l.lane
  FROM races r CROSS JOIN generate_series(1,6) AS l(lane)
  CROSS JOIN q1
  WHERE q1.race_rows=180
    AND q1.nonnull_ids=180
    AND q1.unique_ids=180
),
bounded AS MATERIALIZED (
  SELECT s.race_id, s.lane, e.race_id AS matched_entry,
         CASE WHEN pg_column_size(e.recent_form)<=12000
                   AND octet_length(e.recent_form::text)<=12000
              THEN e.recent_form ELSE NULL::jsonb END AS safe_form
  FROM slots s LEFT JOIN public.v2_race_entries e
    ON e.race_id=s.race_id AND e.lane=s.lane
),
normalized AS MATERIALIZED (
  SELECT matched_entry, safe_form,
         CASE WHEN jsonb_typeof(safe_form)='array' THEN safe_form
              WHEN jsonb_typeof(safe_form->'history')='array'
                THEN safe_form->'history'
              WHEN jsonb_typeof(safe_form->'recent_form')='array'
                THEN safe_form->'recent_form'
              ELSE NULL::jsonb END AS history_array
  FROM bounded
),
item_counts AS (
  SELECT n.matched_entry, n.safe_form, n.history_array,
         jsonb_array_length(n.history_array) AS item_length,
         j.items, j.prior_items, j.current_or_future_items,
         j.missing_or_invalid_date_items, j.numeric_finish_items,
         j.nonnumeric_finish_items, j.official_k_tag_items,
         j.earliest_date, j.latest_date
  FROM normalized n
  LEFT JOIN LATERAL (
    SELECT count(*)::bigint items,
           count(*) FILTER (
             WHERE value->>'race_date' ~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$'
               AND value->>'race_date' < '2025-07-02'
           )::bigint prior_items,
           count(*) FILTER (
             WHERE value->>'race_date' ~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$'
               AND value->>'race_date' >= '2025-07-02'
           )::bigint current_or_future_items,
           count(*) FILTER (
             WHERE value->>'race_date' IS NULL
                OR value->>'race_date' !~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$'
           )::bigint missing_or_invalid_date_items,
           count(*) FILTER (WHERE value->>'finish_position' ~ '^[1-6]$')::bigint numeric_finish_items,
           count(*) FILTER (WHERE value->>'finish_position' IS NULL
                                  OR value->>'finish_position' !~ '^[1-6]$')::bigint nonnumeric_finish_items,
           count(*) FILTER (WHERE value->>'source'='official_k_file')::bigint official_k_tag_items,
           min(value->>'race_date') AS earliest_date,
           max(value->>'race_date') AS latest_date
    FROM jsonb_array_elements(coalesce(n.history_array,'[]'::jsonb)) AS a(value)
  ) j ON TRUE
),
aggregate AS (
  SELECT count(*)::bigint slots,
         count(matched_entry)::bigint joined_entries,
         count(*) FILTER (WHERE safe_form IS NULL)::bigint null_or_over_12kb,
         count(*) FILTER (WHERE item_length=0)::bigint empty_history_slots,
         count(*) FILTER (WHERE item_length BETWEEN 1 AND 5)::bigint nonempty_1_to_5_slots,
         count(*) FILTER (WHERE item_length>5)::bigint over_5_slots,
         count(*) FILTER (WHERE history_array IS NULL)::bigint unrecognized_json_slots,
         coalesce(sum(items),0)::bigint history_items,
         coalesce(sum(prior_items),0)::bigint strict_prior_date_items,
         coalesce(sum(current_or_future_items),0)::bigint same_or_future_date_items,
         coalesce(sum(missing_or_invalid_date_items),0)::bigint invalid_date_items,
         coalesce(sum(numeric_finish_items),0)::bigint numeric_finish_items,
         coalesce(sum(nonnumeric_finish_items),0)::bigint other_finish_items,
         coalesce(sum(official_k_tag_items),0)::bigint official_k_tag_items,
         min(earliest_date) AS earliest_history_date,
         max(latest_date) AS latest_history_date
  FROM item_counts
)
SELECT DATE '2025-07-02' AS day_checked, q.race_rows AS q1_races,
       a.slots, a.joined_entries, a.empty_history_slots,
       a.nonempty_1_to_5_slots, a.over_5_slots,
       a.null_or_over_12kb, a.unrecognized_json_slots,
       a.history_items, a.strict_prior_date_items,
       a.same_or_future_date_items, a.invalid_date_items,
       a.numeric_finish_items, a.other_finish_items,
       a.official_k_tag_items, a.earliest_history_date, a.latest_history_date,
       CASE
         WHEN q.race_rows<>180 OR q.unique_ids<>180 OR q.nonnull_ids<>180
           THEN 'HOLD_Q1_CHANGED'
         WHEN a.slots<>1080 OR a.joined_entries<>1080
           THEN 'HOLD_Q2_POPULATION_OR_DUPLICATE'
         WHEN a.null_or_over_12kb>0 OR a.over_5_slots>0
              OR a.unrecognized_json_slots>0
           THEN 'HOLD_JSON_SIZE_OR_STRUCTURE'
         WHEN a.history_items=0 THEN 'HOLD_NO_HISTORY_ITEMS'
         WHEN a.history_items<>a.strict_prior_date_items
              OR a.same_or_future_date_items>0 OR a.invalid_date_items>0
           THEN 'HOLD_HISTORY_CHRONOLOGY'
         ELSE 'PRIOR_DAY_DATE_SHAPE_ONLY_NOT_CAPTURE_PROOF'
       END AS history_verdict,
       'NO_Q3_REAL_ROI_FORWARD_OR_BUY_AUTHORIZATION'::text AS authorization
FROM q1 q CROSS JOIN aggregate a;
