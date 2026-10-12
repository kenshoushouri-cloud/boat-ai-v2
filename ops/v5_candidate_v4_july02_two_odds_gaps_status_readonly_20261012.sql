-- V5 two previously identified July 2 odds gaps: exact race IDs only.
-- Read-only one SELECT on existing indexed race_id keys, at most 2 outputs.
-- Q3 statuses are diagnostic ONLY, never enter V5 prediction features.
-- No official GET, DB write, data backfill, ROI, or BUY authorization.
WITH targets(race_id) AS (
  VALUES ('20250702_04_09'), ('20250702_13_04')
), records AS MATERIALIZED (
  SELECT t.race_id, r.race_date, r.deadline_at,
         rs.result_status, rs.race_status,
         (rs.trifecta_ticket IS NOT NULL) AS winning_ticket_present,
         (rs.trifecta_payout_yen > 0) AS positive_payout
  FROM targets t
  LEFT JOIN public.v2_races r ON r.race_id=t.race_id
  LEFT JOIN public.v2_results rs ON rs.race_id=t.race_id
), odds AS MATERIALIZED (
  SELECT t.race_id,
         count(o.race_id)::bigint AS odds_rows,
         count(DISTINCT o.ticket)::bigint AS distinct_tickets,
         count(*) FILTER (WHERE o.is_final IS TRUE)::bigint AS final_true_rows,
         count(o.fetched_at)::bigint AS fetched_at_rows,
         min(o.fetched_at) AS earliest_stored_fetch,
         max(o.fetched_at) AS latest_stored_fetch,
         coalesce(string_agg(o.ticket || '=' || o.odds::text, ', ' ORDER BY o.ticket)
                  FILTER (WHERE o.ticket IS NOT NULL), 'NONE') AS stored_ticket_odds
  FROM targets t
  LEFT JOIN public.v2_odds_trifecta o ON o.race_id=t.race_id
  GROUP BY t.race_id
), participants AS MATERIALIZED (
  SELECT t.race_id,
         count(e.race_id)::bigint AS result_entry_rows,
         count(DISTINCT e.lane)::bigint AS unique_result_lanes,
         count(*) FILTER (
           WHERE e.finish_status IN ('F','L0','L1','K0','K1','S0','S1','S2')
             OR e.is_flying IS TRUE OR e.is_late IS TRUE
         )::bigint AS flagged_result_entries
  FROM targets t
  LEFT JOIN public.v2_result_entries e ON e.race_id=t.race_id
  GROUP BY t.race_id
)
SELECT rec.race_id, rec.race_date,
       (rec.deadline_at IS NOT NULL) AS deadline_present,
       rec.result_status, rec.race_status,
       rec.winning_ticket_present, rec.positive_payout,
       p.result_entry_rows, p.unique_result_lanes, p.flagged_result_entries,
       o.odds_rows, o.distinct_tickets, o.final_true_rows,
       o.fetched_at_rows, o.earliest_stored_fetch, o.latest_stored_fetch,
       CASE WHEN o.odds_rows BETWEEN 0 AND 2 THEN o.stored_ticket_odds
            ELSE 'UNEXPECTED_MORE_THAN_TWO_ROWS_REVIEW' END AS stored_ticket_odds,
       CASE WHEN rec.race_date<>DATE '2025-07-02' OR rec.race_date IS NULL
             THEN 'HOLD_RACE_LOOKUP_OR_DATE'
            WHEN o.odds_rows=0 THEN 'HOLD_ZERO_ODDS_SOURCE_OR_ETL_UNKNOWN'
            WHEN o.odds_rows=2 THEN 'HOLD_TWO_ODDS_PARSER_OR_SOURCE_UNKNOWN'
            ELSE 'HOLD_ODDS_COUNT_CHANGED'
       END AS diagnostic_verdict,
       'NO_Q3_PREDICTION_REPAIR_ROI_FORWARD_OR_BUY'::text AS authorization
FROM records rec
JOIN odds o ON o.race_id=rec.race_id
JOIN participants p ON p.race_id=rec.race_id
ORDER BY rec.race_id;
