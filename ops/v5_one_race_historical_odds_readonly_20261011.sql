-- V5 ONE-race historical closing-odds SAMPLE (2026-10-11 JST).
-- READ ONLY: one bounded SELECT statement; no DDL, write, external GET, or new services.
-- Selects the latest one actually stored race ID in the already-validated
-- historical 2026-10-01 .. 2026-10-05 period; never scans full row details.
-- If no race is returned, the sample is absent; DO NOT infer all dates missing.
-- Prerequisite: table v2_odds_trifecta has index leading with race_id,
-- e.g. ux_v2_odds_trifecta_race_ticket (inspect schema FIRST).
-- Do not run on the incorrect PostgreSQL service; do not use on a busy DB.
-- is_final and fetched_at are stored source flags, not official first-write proof.
-- This SQL does NOT compute ROI or certify predeadline purchasable odds.

WITH picked AS MATERIALIZED (
  SELECT race_id
    FROM public.v2_odds_trifecta
   WHERE race_id >= '20261001_'
     AND race_id <  '20261006_'
   ORDER BY race_id DESC
   LIMIT 1
),
odds AS MATERIALIZED (
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
    JOIN picked p ON p.race_id = o.race_id
   GROUP BY o.race_id
),
k AS MATERIALIZED (
  SELECT e.race_id, count(*)::int AS entry_rows,
         count(*) FILTER (WHERE e.is_flying IS TRUE)::int AS flying_lanes,
         count(*) FILTER (WHERE e.is_late IS TRUE)::int AS late_lanes
    FROM public.v2_result_entries e
    JOIN picked p ON p.race_id = e.race_id
   GROUP BY e.race_id
)
SELECT p.race_id,
       o.odds_rows, o.distinct_tickets, o.valid_tickets,
       o.final_true, o.final_false, o.final_null,
       o.oldest_fetch, o.newest_fetch,
       CASE WHEN o.odds_rows = 120
                 AND o.distinct_tickets = 120
                 AND o.valid_tickets = 120
                 AND o.final_true = 120
                 AND o.final_false = 0
                 AND o.final_null = 0
            THEN 'CANDIDATE_120_FINAL_FLAGS_NOT_PROVEN_ORIGINAL'
            ELSE 'INCOMPLETE_MIXED_OR_NONFINAL'
        END AS closing_odds_coverage,
       r.result_status, r.race_status,
       (r.trifecta_ticket IS NOT NULL) AS has_trifecta_ticket,
       (r.trifecta_payout_yen > 0) AS has_positive_payout,
       coalesce(k.entry_rows,0) AS entry_rows,
       coalesce(k.flying_lanes,0) AS flying_lanes,
       coalesce(k.late_lanes,0) AS late_lanes,
       FALSE AS independently_verified_predeadline_capture,
       FALSE AS verified_refund_ticket_mapping,
       FALSE AS verified_v5_roi,
       FALSE AS buy_eligible
  FROM picked p
  JOIN odds o ON o.race_id = p.race_id
  LEFT JOIN public.v2_results r ON r.race_id = p.race_id
  LEFT JOIN k ON k.race_id = p.race_id;
