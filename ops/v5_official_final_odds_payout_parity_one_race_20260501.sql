-- V5 next ONE step: compare archived final-flag odds with official result
-- winning 3-ren-tan ticket and payout for 2026-05-01 Omura 12R.
-- Read-only, exact race_id and ticket lookups, no DDL/DML.
-- is_final is ingestion flag, NOT independent official source proof.
-- Refund/VOID, predeadline candidate/odds, actual V5 ROI and BUY unverified.
-- 3-ren-tan decimal odds x JPY100 = payout per JPY100 of winning ticket.
WITH settle AS MATERIALIZED (
  SELECT race_id, result_status, race_status,
         trifecta_ticket, trifecta_payout_yen
    FROM public.v2_results
   WHERE race_id = '20260501_24_12'
),
winner_odds AS MATERIALIZED (
  SELECT o.race_id, o.ticket, o.odds, o.is_final, o.fetched_at
    FROM public.v2_odds_trifecta o
    JOIN settle s
      ON o.race_id = s.race_id AND o.ticket = s.trifecta_ticket
)
SELECT s.race_id, s.result_status, s.race_status,
       s.trifecta_ticket AS winning_ticket,
       s.trifecta_payout_yen AS stored_official_result_payout_yen,
       w.ticket IS NOT NULL AS winner_odds_row_present,
       w.odds AS stored_winner_odds,
       w.is_final AS stored_winner_is_final,
       w.fetched_at AS odds_fetch_recorded_at,
       CASE WHEN w.odds > 0
                 AND w.odds::text NOT IN ('NaN','Infinity','-Infinity')
            THEN round(w.odds::numeric * 100, 0)::bigint
            ELSE NULL END AS implied_payout_per_100_yen,
       CASE WHEN w.odds > 0
                 AND w.odds::text NOT IN ('NaN','Infinity','-Infinity')
                 AND s.trifecta_payout_yen > 0
            THEN s.trifecta_payout_yen::numeric - round(w.odds::numeric * 100, 0)
            ELSE NULL END AS payout_difference_yen,
       CASE
         WHEN lower(coalesce(s.result_status,'')) <> 'official'
           OR lower(coalesce(s.race_status,'')) <> 'official'
           THEN 'UNRESOLVED_RESULT_STATUS'
         WHEN s.trifecta_ticket IS NULL OR s.trifecta_payout_yen <= 0
           THEN 'WINNING_TICKET_OR_PAYOUT_MISSING'
         WHEN w.ticket IS NULL OR w.is_final IS DISTINCT FROM TRUE
           THEN 'WINNING_ODDS_ABSENT_OR_NOT_FINAL_FLAG'
         WHEN w.odds IS NULL OR w.odds <= 0
           OR w.odds::text IN ('NaN','Infinity','-Infinity')
           THEN 'WINNING_ODDS_INVALID'
         WHEN round(w.odds::numeric * 100, 0) = s.trifecta_payout_yen
           THEN 'STORED_ODDS_AND_PAYOUT_NUMERIC_PARITY_ONLY'
         ELSE 'STORED_ODDS_PAYOUT_DISCREPANCY_REVIEW'
       END AS result_odds_parity,
       FALSE AS official_raw_html_authenticated,
       FALSE AS predeadline_decision_price_verified,
       FALSE AS f_l_refund_tickets_verified,
       FALSE AS v5_real_roi_verified,
       FALSE AS buy_eligible
  FROM settle s
  LEFT JOIN winner_odds w ON w.race_id = s.race_id;
