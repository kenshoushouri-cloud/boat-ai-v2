-- V5 2025-07-01 recent_form prior-day DATE SHAPE audit.
-- Railway boat-v2-postgres > production > postgres-hobby-fullhistory-candidate-v4 > Data > Query.
-- ONE SELECT, exactly 144 Q1 unique races x 6 entry slots, one aggregate output.
-- No exhibition, Q3, results, payouts, odds, row IDs or database changes.
-- DATE-ONLY PRIOR history (even if valid) is retrospective reconstruction,
-- NOT independently attested historical first capture.
-- Maximum client projection is one summary row; database size guard 12KB JSON.
WITH races AS MATERIALIZED (
  SELECT race_id FROM public.v2_races
  WHERE race_date = DATE '2025-07-01'
),
q1 AS MATERIALIZED (
  SELECT count(*)::bigint n, count(race_id)::bigint nonnull,
         count(DISTINCT race_id)::bigint unique_ids FROM races
),
slots AS MATERIALIZED (
  SELECT r.race_id, k.lane
  FROM races r CROSS JOIN generate_series(1,6) AS k(lane)
  CROSS JOIN q1
  WHERE q1.n=144 AND q1.nonnull=144 AND q1.unique_ids=144
),
bounded AS MATERIALIZED (
  SELECT s.race_id, s.lane, e.race_id AS matched_entry,
         CASE WHEN pg_column_size(e.recent_form) <= 12000
                   AND octet_length(e.recent_form::text) <= 12000
              THEN e.recent_form ELSE NULL::jsonb END AS safe_form
  FROM slots s
  LEFT JOIN public.v2_race_entries e
    ON e.race_id=s.race_id AND e.lane=s.lane
),
normalized AS MATERIALIZED (
  SELECT matched_entry, safe_form,
         CASE
           WHEN jsonb_typeof(safe_form)='array' THEN safe_form
           WHEN jsonb_typeof(safe_form->'history')='array'
             THEN safe_form->'history'
           WHEN jsonb_typeof(safe_form->'recent_form')='array'
             THEN safe_form->'recent_form'
           ELSE NULL::jsonb
         END AS history_array
  FROM bounded
),
checked AS (
  SELECT n.matched_entry, n.safe_form, n.history_array,
         h.items, h.prior_items, h.not_prior_items,
         h.invalid_date_items, h.invalid_finish_items,
         h.official_k_tag_items, h.newest_prior_date
  FROM normalized n
  LEFT JOIN LATERAL (
    SELECT count(*)::bigint AS items,
           count(*) FILTER (
             WHERE value->>'race_date' ~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$'
               AND value->>'race_date' < '2025-07-01'
           )::bigint AS prior_items,
           count(*) FILTER (
             WHERE value->>'race_date' >= '2025-07-01'
           )::bigint AS not_prior_items,
           count(*) FILTER (
             WHERE value->>'race_date' IS NULL
                OR value->>'race_date' !~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$'
           )::bigint AS invalid_date_items,
           count(*) FILTER (
             WHERE value->>'finish_position' IS NULL
                OR value->>'finish_position' !~ '^[1-6]$'
           )::bigint AS invalid_finish_items,
           count(*) FILTER (
             WHERE value->>'source'='official_k_file'
           )::bigint AS official_k_tag_items,
           max(value->>'race_date') FILTER (
             WHERE value->>'race_date' < '2025-07-01'
               AND value->>'race_date' ~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$'
           ) AS newest_prior_date
    FROM jsonb_array_elements(coalesce(n.history_array,'[]'::jsonb)) item(value)
  ) h ON TRUE
),
summary AS (
  SELECT count(*)::bigint joined_slots,
         count(matched_entry)::bigint joined_entries,
         count(*) FILTER (WHERE safe_form IS NULL)::bigint missing_or_over_12kb_form,
         count(*) FILTER (WHERE items BETWEEN 1 AND 5)::bigint one_to_five_history_slots,
         coalesce(sum(items),0)::bigint history_items,
         coalesce(sum(prior_items),0)::bigint prior_date_items,
         coalesce(sum(not_prior_items),0)::bigint current_or_future_date_items,
         coalesce(sum(invalid_date_items),0)::bigint invalid_date_items,
         coalesce(sum(invalid_finish_items),0)::bigint invalid_finish_items,
         coalesce(sum(official_k_tag_items),0)::bigint official_k_source_tag_items,
         max(newest_prior_date) AS latest_prior_date_seen
  FROM checked
)
SELECT DATE '2025-07-01' AS race_date_checked,
       q1.n AS q1_races_rechecked,
       s.joined_slots, s.joined_entries, s.missing_or_over_12kb_form,
       s.one_to_five_history_slots, s.history_items, s.prior_date_items,
       s.current_or_future_date_items, s.invalid_date_items,
       s.invalid_finish_items, s.official_k_source_tag_items,
       s.latest_prior_date_seen,
       CASE
         WHEN q1.n<>144 OR q1.nonnull<>144 OR q1.unique_ids<>144
           THEN 'HOLD_Q1_CHANGED'
         WHEN s.joined_slots<>864 OR s.joined_entries<>864
           THEN 'HOLD_Q2_ENTRY_POPULATION'
         WHEN s.missing_or_over_12kb_form<>0 OR s.one_to_five_history_slots<>864
           THEN 'HOLD_RECENT_FORM_MISSING_OVERSIZE_OR_LENGTH'
         WHEN s.history_items<>s.prior_date_items
           OR s.current_or_future_date_items<>0
           OR s.invalid_date_items<>0 OR s.invalid_finish_items<>0
           THEN 'HOLD_RECENT_FORM_DATE_OR_FINISH'
         ELSE 'PRIOR_DATE_SHAPE_ONLY_NOT_CAPTURE_PROOF'
       END AS recent_form_verdict,
       'NO_EXHIBITION_Q3_ROI_FORWARD_OR_BUY_AUTHORIZATION'::text AS authorization
FROM q1 CROSS JOIN summary s;
