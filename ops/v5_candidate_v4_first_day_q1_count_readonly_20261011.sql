-- V5 Q1 real-data first-day SMOKE: aggregate only, no race IDs or result data.
-- Railway > boat-v2-postgres > production >
-- postgres-hobby-fullhistory-candidate-v4 > Data > Query.
-- Run ONLY after confirming the service and catalog type/index checks.
-- ONE SELECT, completed date 2025-07-01 only, index prefix race_date verified.
-- No UPDATE/DDL, LIMIT/DISTINCT row filtering or full-period history scan.
-- Zero rows CANNOT be classified as a confirmed holiday.
SELECT DATE '2025-07-01' AS race_date_checked,
       count(*)::bigint AS q1_inventory_rows,
       count(DISTINCT r.race_id)::bigint AS unique_race_ids,
       CASE
         WHEN count(*) = 0 THEN 'HOLD_EMPTY_DAY_NOT_HOLIDAY_PROOF'
         WHEN count(*) > 400 THEN 'HOLD_DAY_OVER_400_RACES'
         WHEN count(r.race_id) <> count(*) THEN 'HOLD_NULL_RACE_ID'
         WHEN count(DISTINCT r.race_id) <> count(*) THEN 'HOLD_DUPLICATE_RACE_ID'
         ELSE 'Q1_ONE_DAY_COUNT_ONLY_NOT_COVERAGE_PROOF'
       END AS q1_verdict,
       'NO_Q2_Q3_OR_BUY_AUTHORIZATION'::text AS next_action_authorization
FROM public.v2_races r
WHERE r.race_date = DATE '2025-07-01';
