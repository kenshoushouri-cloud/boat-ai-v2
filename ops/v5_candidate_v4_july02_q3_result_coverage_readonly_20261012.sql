-- V5 Q3 postrace settlement coverage: 2025-07-02 ONLY.
-- Railway boat-v2-postgres / production / postgres-hobby-fullhistory-candidate-v4 / Data > Query.
-- One read-only SELECT returning one aggregate row; Q1 expected 180 distinct race IDs.
-- Joins only v2_races and v2_results on preflight-verified btree race_id.
-- Q3 NEVER joins into Q2/predictions or future-day historical model fitting.
-- These counts are NOT evidence of official refund/VOID resolution, authentic
-- source bytes, actual predeadline odds or V5 ROI. No DB writes or personal data.
WITH races AS MATERIALIZED (
  SELECT race_id FROM public.v2_races
  WHERE race_date=DATE '2025-07-02'
),
q1 AS MATERIALIZED (
  SELECT count(*)::bigint n, count(race_id)::bigint nonnull_ids,
         count(DISTINCT race_id)::bigint unique_ids FROM races
),
eligible AS MATERIALIZED (
  SELECT r.race_id FROM races r CROSS JOIN q1
  WHERE q1.n=180 AND q1.nonnull_ids=180 AND q1.unique_ids=180
),
per_race AS (
  SELECT r.race_id,
         count(rs.race_id)::bigint result_rows,
         count(rs.trifecta_ticket)::bigint ticket_rows,
         count(*) FILTER (
           WHERE d.digits ~ '^[1-6]{3}$'
             AND substring(d.digits,1,1)<>substring(d.digits,2,1)
             AND substring(d.digits,1,1)<>substring(d.digits,3,1)
             AND substring(d.digits,2,1)<>substring(d.digits,3,1)
         )::bigint valid_ticket_rows,
         count(rs.trifecta_payout_yen)::bigint payout_rows,
         count(*) FILTER (
           WHERE rs.trifecta_payout_yen IS NOT NULL
             AND rs.trifecta_payout_yen > 0
         )::bigint positive_payout_rows,
         count(*) FILTER (WHERE rs.result_status='official')::bigint result_status_official,
         count(*) FILTER (WHERE rs.race_status='official')::bigint race_status_official,
         count(*) FILTER (
           WHERE rs.race_id IS NOT NULL
             AND (rs.result_status IS NULL OR rs.race_status IS NULL)
         )::bigint null_status_rows
  FROM eligible r
  LEFT JOIN public.v2_results rs ON rs.race_id=r.race_id
  LEFT JOIN LATERAL (
    SELECT CASE WHEN octet_length(rs.trifecta_ticket)<=24
                THEN regexp_replace(rs.trifecta_ticket,'[^0-9]','','g')
                ELSE NULL::text END AS digits
  ) d ON TRUE
  GROUP BY r.race_id
),
totals AS (
  SELECT count(*)::bigint inventory_races,
         count(*) FILTER (WHERE result_rows=0)::bigint missing_result_races,
         count(*) FILTER (WHERE result_rows>1)::bigint duplicate_result_races,
         coalesce(sum(result_rows),0)::bigint result_rows,
         coalesce(sum(ticket_rows),0)::bigint trifecta_ticket_rows,
         coalesce(sum(valid_ticket_rows),0)::bigint valid_unique_trifecta_rows,
         coalesce(sum(payout_rows),0)::bigint payout_nonnull_rows,
         coalesce(sum(positive_payout_rows),0)::bigint positive_payout_rows,
         coalesce(sum(result_status_official),0)::bigint official_result_status_rows,
         coalesce(sum(race_status_official),0)::bigint official_race_status_rows,
         coalesce(sum(null_status_rows),0)::bigint missing_status_rows
  FROM per_race
)
SELECT DATE '2025-07-02' AS day_checked,
       q.n AS q1_races_rechecked, t.inventory_races, t.result_rows,
       t.missing_result_races, t.duplicate_result_races,
       t.trifecta_ticket_rows, t.valid_unique_trifecta_rows,
       t.payout_nonnull_rows, t.positive_payout_rows,
       t.official_result_status_rows, t.official_race_status_rows,
       t.missing_status_rows,
       CASE WHEN q.n<>180 OR q.nonnull_ids<>180 OR q.unique_ids<>180
              THEN 'HOLD_Q1_CHANGED'
            WHEN t.inventory_races<>180 OR t.missing_result_races>0
                 OR t.duplicate_result_races>0 OR t.result_rows<>180
              THEN 'HOLD_Q3_RESULT_POPULATION'
            WHEN t.trifecta_ticket_rows<>180
                 OR t.valid_unique_trifecta_rows<>180
                 OR t.payout_nonnull_rows<>180
              THEN 'HOLD_Q3_REFUND_VOID_OR_PAYLOAD_REVIEW'
            ELSE 'Q3_NUMERIC_COVERAGE_ONLY_SETTLEMENT_UNVERIFIED'
       END AS q3_verdict,
       'NO_AUTHORIZATION_FOR_REAL_ROI_FORWARD_OR_BUY'::text AS authorization
FROM q1 q CROSS JOIN totals t;
