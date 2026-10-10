-- V5 closing-odds classification: one stored historical race, 2026-05-01.
-- READ ONLY, one SELECT, no modification, no deploy, no web GET.
-- Run ONLY on known correct historical PostgreSQL service when it is responsive.
-- Uses race_id-leading index; selects latest one existing race in one day's
-- odds rows, then reads at most that race's 120-ticket snapshot.
-- Historical is_final=true is only an ingestion FLAG (not independently
-- authenticated official closing-price source); fetched_at is retrieval time.
-- Do not use a closing price as a predictor's predeadline input.
-- If zero rows: May 1 has no matching odds rows on THIS database;
-- do not infer an entire month/history is absent.

WITH picked AS MATERIALIZED (
  SELECT race_id
    FROM public.v2_odds_trifecta
   WHERE race_id >= '20260501_'
     AND race_id <  '20260502_'
   ORDER BY race_id DESC
   LIMIT 1
),
sample AS MATERIALIZED (
  SELECT o.race_id,
         count(*)::int AS odds_rows,
         count(DISTINCT o.ticket)::int AS distinct_tickets,
         count(*) FILTER (
            WHERE o.ticket ~ '^[1-6]-[1-6]-[1-6]$'
              AND split_part(o.ticket,'-',1) <> split_part(o.ticket,'-',2)
              AND split_part(o.ticket,'-',1) <> split_part(o.ticket,'-',3)
              AND split_part(o.ticket,'-',2) <> split_part(o.ticket,'-',3)
              AND o.odds > 0
              AND o.odds::text NOT IN ('NaN','Infinity','-Infinity')
         )::int AS valid_tickets,
         count(*) FILTER (WHERE o.is_final IS TRUE)::int AS final_true,
         count(*) FILTER (WHERE o.is_final IS FALSE)::int AS final_false,
         count(*) FILTER (WHERE o.is_final IS NULL)::int AS final_null,
         min(o.fetched_at) AS oldest_fetch,
         max(o.fetched_at) AS newest_fetch
    FROM public.v2_odds_trifecta o
    JOIN picked p ON o.race_id = p.race_id
   GROUP BY o.race_id
)
SELECT s.race_id, s.odds_rows, s.distinct_tickets, s.valid_tickets,
       s.final_true, s.final_false, s.final_null,
       s.oldest_fetch, s.newest_fetch,
       r.deadline_at,
       CASE
         WHEN s.odds_rows <> 120
           OR s.valid_tickets <> 120
           OR s.distinct_tickets <> 120
           THEN 'INVALID_OR_INCOMPLETE_120'
         WHEN s.final_true = 120
           THEN 'COMPLETE_120_FINAL_FLAG_ONLY'
         WHEN s.final_false = 120
           THEN 'COMPLETE_120_NONFINAL_FLAG_ONLY'
         ELSE 'COMPLETE_120_FLAGS_MIXED_OR_NULL'
       END AS odds_classification,
       res.result_status, res.race_status,
       (res.trifecta_ticket IS NOT NULL) AS has_winning_ticket,
       (res.trifecta_payout_yen > 0) AS has_positive_payout,
       FALSE AS original_official_odds_verified,
       FALSE AS predeadline_decision_price_verified,
       FALSE AS v5_real_roi_verified,
       FALSE AS buy_eligible
  FROM sample s
  LEFT JOIN public.v2_races r ON r.race_id = s.race_id
  LEFT JOIN public.v2_results res ON res.race_id = s.race_id;
