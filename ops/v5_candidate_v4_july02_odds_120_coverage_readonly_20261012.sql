-- V5 2025-07-02 historical trifecta ODDS COVERAGE: one research day ONLY.
-- Railway / boat-v2-postgres / production /
-- postgres-hobby-fullhistory-candidate-v4 > Data > Query.
-- PREREQUISITE met in user live metadata: 5/5 compatible columns,
-- SELECT privilege and valid nonpartial race_id-leading btree index.
-- Read-only ONE SELECT; 180 previously verified unique races.
-- Indexed join to existing odds: EXPECT ~180 x 120 = 21,600 rows.
-- No raw odds, race IDs, individual tickets, DML, DDL or Q3/result reads.
-- Do not use fetched_at or is_final as original cutoff-time truth.
-- Count gaps/duplicates: NEVER silently take LIMIT 120 or arbitrary tickets.
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
eligible AS MATERIALIZED (
  SELECT r.race_id FROM races r CROSS JOIN q1
  WHERE q1.race_rows=180 AND q1.nonnull_ids=180 AND q1.unique_ids=180
),
per_race AS (
  SELECT r.race_id,
         count(o.race_id)::bigint n,
         count(DISTINCT o.ticket)::bigint unique_tickets,
         count(*) FILTER (
           WHERE o.ticket ~ '^[1-6]-[1-6]-[1-6]$'
             AND split_part(o.ticket,'-',1)<>split_part(o.ticket,'-',2)
             AND split_part(o.ticket,'-',1)<>split_part(o.ticket,'-',3)
             AND split_part(o.ticket,'-',2)<>split_part(o.ticket,'-',3)
             AND o.odds>0
             AND o.odds::text NOT IN ('NaN','Infinity','-Infinity')
         )::bigint valid_ticket_and_odds_rows,
         count(*) FILTER (WHERE o.is_final IS TRUE)::bigint final_true,
         count(*) FILTER (WHERE o.is_final IS FALSE)::bigint final_false,
         count(*) FILTER (WHERE o.race_id IS NOT NULL AND o.is_final IS NULL)::bigint final_unknown,
         count(o.fetched_at)::bigint fetch_timestamp_present,
         min(o.fetched_at) AS earliest_stored_fetch,
         max(o.fetched_at) AS latest_stored_fetch
  FROM eligible r
  LEFT JOIN public.v2_odds_trifecta o ON o.race_id=r.race_id
  GROUP BY r.race_id
),
summary AS (
  SELECT count(*)::bigint races_checked,
         coalesce(sum(n),0)::bigint stored_odds_rows,
         coalesce(sum(unique_tickets),0)::bigint unique_ticket_rows_across_races,
         coalesce(sum(valid_ticket_and_odds_rows),0)::bigint valid_ticket_and_positive_odds_rows,
         count(*) FILTER (WHERE n=0)::bigint races_with_no_odds,
         count(*) FILTER (WHERE n<>120)::bigint races_not_exactly_120,
         count(*) FILTER (
           WHERE n=120 AND unique_tickets=120 AND valid_ticket_and_odds_rows=120
         )::bigint races_complete_120_unique_valid,
         count(*) FILTER (
           WHERE n=120 AND unique_tickets=120 AND valid_ticket_and_odds_rows=120
             AND final_true=120 AND final_false=0 AND final_unknown=0
         )::bigint races_complete_120_final_flag,
         coalesce(sum(final_true),0)::bigint final_true_rows,
         coalesce(sum(final_false),0)::bigint final_false_rows,
         coalesce(sum(final_unknown),0)::bigint final_unknown_rows,
         coalesce(sum(fetch_timestamp_present),0)::bigint fetched_at_present_rows,
         min(earliest_stored_fetch) AS earliest_stored_fetch,
         max(latest_stored_fetch) AS latest_stored_fetch
  FROM per_race
)
SELECT DATE '2025-07-02' AS day_checked,
       q1.race_rows AS q1_races_rechecked,
       s.races_checked,
       21600::bigint AS expected_120_odds_rows,
       s.stored_odds_rows,
       s.unique_ticket_rows_across_races,
       s.valid_ticket_and_positive_odds_rows,
       s.races_with_no_odds,
       s.races_not_exactly_120,
       s.races_complete_120_unique_valid,
       s.races_complete_120_final_flag,
       s.final_true_rows, s.final_false_rows, s.final_unknown_rows,
       s.fetched_at_present_rows,
       s.earliest_stored_fetch, s.latest_stored_fetch,
       CASE
         WHEN q1.race_rows<>180 OR q1.nonnull_ids<>180 OR q1.unique_ids<>180
           THEN 'HOLD_Q1_CHANGED'
         WHEN s.races_checked<>180
           THEN 'HOLD_ODDS_RACE_COHORT_CHANGED'
         WHEN s.stored_odds_rows<>21600
           OR s.races_complete_120_unique_valid<>180
           THEN 'HOLD_ODDS_120_MISSING_DUPLICATE_OR_INVALID'
         WHEN s.races_complete_120_final_flag<>180
           THEN 'ODDS_120_SHAPE_OK_FINAL_FLAG_MIXED_NOT_CLOSING_PROOF'
         ELSE 'ODDS_120_COMPLETE_FINAL_FLAG_ONLY_NOT_ASOF_PROOF'
       END AS odds_verdict,
       'NO_Q3_REAL_ROI_FORWARD_OR_BUY_AUTHORIZATION'::text AS authorization
FROM q1 CROSS JOIN summary s;
