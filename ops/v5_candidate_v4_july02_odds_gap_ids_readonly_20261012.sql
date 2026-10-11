-- Research odds gap IDs: 2025-07-02 only, Railway candidate-v4 Data > Query.
-- Read-only single SELECT. Returns only race IDs with incomplete odds.
-- Q1 must remain exactly 180 unique race IDs. The prior count was 178 full/180.
-- Do not repair, omit races from ROI denominator, or infer predeadline odds.
WITH races AS MATERIALIZED (
  SELECT race_id FROM public.v2_races WHERE race_date=DATE '2025-07-02'
), q1 AS MATERIALIZED (
  SELECT count(*)::bigint n, count(race_id)::bigint nonnull,
         count(DISTINCT race_id)::bigint unique_ids FROM races
), checked AS MATERIALIZED (
  SELECT r.race_id FROM races r CROSS JOIN q1
  WHERE q1.n=180 AND q1.nonnull=180 AND q1.unique_ids=180
), counts AS (
  SELECT r.race_id, count(o.race_id)::bigint odds_rows,
         count(DISTINCT o.ticket)::bigint distinct_tickets,
         count(*) FILTER (WHERE o.is_final IS TRUE)::bigint final_true,
         count(o.fetched_at)::bigint fetched_at_rows
  FROM checked r LEFT JOIN public.v2_odds_trifecta o
       ON o.race_id=r.race_id
  GROUP BY r.race_id
)
SELECT DATE '2025-07-02' AS day_checked, q.n AS races_rechecked,
       c.race_id, c.odds_rows,
       (120-c.odds_rows)::bigint AS missing_from_120,
       c.distinct_tickets, c.final_true, c.fetched_at_rows,
       'HOLD_GAP_NEEDS_SOURCE_REVIEW'::text AS gap_verdict,
       'NO_REPAIR_ROI_FORWARD_OR_BUY'::text AS authorization
FROM q1 q CROSS JOIN counts c
WHERE c.odds_rows<>120 OR c.distinct_tickets<>120 OR c.final_true<>120
ORDER BY c.race_id;
