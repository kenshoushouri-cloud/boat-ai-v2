-- V5 2025-07-02: classify the 10 non-1..6 historical finish values.
-- Railway production / postgres-hobby-fullhistory-candidate-v4 / Data > Query.
-- ONE read-only SELECT; indexed single-day 180 races, six lanes, JSON <=12 KB.
-- Only aggregated finish_position / finish_status codes; no racer/race IDs or raw histories.
-- Stored K source tags and dates are NOT proof of authentic original source bytes.
-- Do NOT turn F/L/事故/返還/欠場 into normal losing finishes or erase them.
WITH races AS MATERIALIZED (
  SELECT race_id FROM public.v2_races
  WHERE race_date=DATE '2025-07-02'
),
q1 AS MATERIALIZED (
  SELECT count(*)::bigint n, count(race_id)::bigint nonnull,
         count(DISTINCT race_id)::bigint unique_ids FROM races
),
slots AS MATERIALIZED (
  SELECT r.race_id, l.lane
  FROM races r CROSS JOIN generate_series(1,6) AS l(lane)
  CROSS JOIN q1 WHERE q1.n=180 AND q1.nonnull=180 AND q1.unique_ids=180
),
forms AS MATERIALIZED (
  SELECT e.race_id AS matched_entry,
         CASE WHEN pg_column_size(e.recent_form)<=12000
                AND octet_length(e.recent_form::text)<=12000
              THEN e.recent_form ELSE NULL::jsonb END AS form
  FROM slots s LEFT JOIN public.v2_race_entries e
    ON e.race_id=s.race_id AND e.lane=s.lane
),
items AS MATERIALIZED (
  SELECT a.value AS item
  FROM forms f CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(f.form)='array' THEN f.form
         WHEN jsonb_typeof(f.form->'history')='array' THEN f.form->'history'
         WHEN jsonb_typeof(f.form->'recent_form')='array' THEN f.form->'recent_form'
         ELSE '[]'::jsonb END
  ) AS a(value)
),
abnormal AS MATERIALIZED (
  SELECT item->>'finish_position' AS position_text,
         item->>'finish_status' AS status_text,
         item->>'race_date' AS history_date,
         item->>'source' AS source_name
  FROM items
  WHERE item->>'finish_position' IS NULL
     OR item->>'finish_position' !~ '^[1-6]$'
),
shape AS (
  SELECT count(*)::bigint slots_seen,
         count(matched_entry)::bigint joined_entries,
         count(*) FILTER (WHERE form IS NULL)::bigint null_or_over12k
  FROM forms
),
totals AS (
  SELECT count(*)::bigint abnormal_items,
         count(*) FILTER (
           WHERE history_date <> '2025-07-01'
              OR history_date IS NULL
         )::bigint unexpected_dates,
         count(*) FILTER (
           WHERE source_name <> 'official_k_file'
              OR source_name IS NULL
         )::bigint non_k_tags
  FROM abnormal
),
codes AS (
  SELECT CASE WHEN position_text IS NULL THEN 'NULL'
              WHEN position_text='' THEN 'EMPTY'
              WHEN length(position_text)>12 THEN 'LONG_VALUE'
              ELSE position_text END AS finish_position_code,
         CASE WHEN status_text IS NULL THEN 'NULL'
              WHEN status_text='' THEN 'EMPTY'
              WHEN length(status_text)>12 THEN 'LONG_VALUE'
              ELSE status_text END AS finish_status_code,
         count(*)::bigint AS event_count
  FROM abnormal
  GROUP BY 1,2
)
SELECT DATE '2025-07-02' AS target_day,
       q.n AS q1_races,
       sh.slots_seen, sh.joined_entries,
       t.abnormal_items, t.unexpected_dates, t.non_k_tags,
       coalesce(c.finish_position_code,'NONE') AS finish_position_code,
       coalesce(c.finish_status_code,'NONE') AS finish_status_code,
       coalesce(c.event_count,0)::bigint AS count_at_code,
       CASE WHEN q.n<>180 OR q.nonnull<>180 OR q.unique_ids<>180
             THEN 'HOLD_Q1_CHANGED'
            WHEN sh.slots_seen<>1080 OR sh.joined_entries<>1080 OR sh.null_or_over12k>0
             THEN 'HOLD_Q2_SOURCE_SHAPE'
            WHEN t.abnormal_items<>10 OR t.unexpected_dates>0 OR t.non_k_tags>0
             THEN 'HOLD_SPECIAL_FINISH_POPULATION_CHANGED'
            ELSE 'SPECIAL_FINISH_CODE_COUNTS_ONLY_REVIEW_REQUIRED'
       END AS code_verdict,
       'NO_Q3_ROI_FORWARD_OR_BUY_AUTHORIZATION'::text AS authorization
FROM q1 q CROSS JOIN shape sh CROSS JOIN totals t
LEFT JOIN codes c ON TRUE
ORDER BY c.event_count DESC NULLS LAST, c.finish_position_code, c.finish_status_code;
