-- V5 one-day research input adapter PRECONDITION: map result/refund evidence.
-- Structural metadata + bounded 2026-10-20 result-status populations only.
-- Never infer "no refund" from an absent/null column, normal finish, or
-- 'official' result status. NO LIVE/Forward/BET/BUY eligibility from this.
-- No DB writes, first-capture promotion, collector changes, or bulk scan.
-- ConoHa psql:
--   sudo -u postgres psql -d railway -X -v ON_ERROR_STOP=1 \
--     -v day=2026-10-20 -f /tmp/v5_result_refund_sources.sql
\set ON_ERROR_STOP on
\pset pager off
\if :{?day}
\else
\set day 2026-10-20
\endif
BEGIN TRANSACTION READ ONLY;
SET LOCAL lock_timeout='1000ms';
SET LOCAL statement_timeout='15000ms';
SET LOCAL work_mem='8MB';

-- 1) Detect, not assume, the available result/refund/incident source columns.
SELECT table_schema||'.'||table_name AS relation,
       column_name, data_type
FROM information_schema.columns
WHERE table_schema='public'
  AND table_name IN (
    'v2_results','v2_result_entries','v2_races',
    'v2_realtime_exhibition_snapshots'
  )
  AND column_name ~* (
    'result|race_status|incident|refund|return|void|cancel|'
    ||'trifecta|payout|raw|is_flying|is_late|finish_status|'
    ||'start_course|fetched_at|snapshot_at|snapshot_label'
  )
ORDER BY relation,column_name
LIMIT 90;

-- 2) The complete one-day status distribution; no postrace status becomes
-- an input to historical predeadline racing decisions.
WITH one_day AS MATERIALIZED (
  SELECT to_jsonb(rs) AS doc
  FROM boat_data.races r
  JOIN public.v2_results rs ON rs.race_id=r.race_id
  WHERE r.race_date=:'day'::date
    AND r.race_date>=DATE '2025-07-01'
)
SELECT coalesce(nullif(doc->>'result_status',''),'(MISSING)') AS result_status,
       coalesce(nullif(doc->>'race_status',''),'(MISSING)') AS race_status,
       count(*) AS races
FROM one_day
GROUP BY 1,2
ORDER BY races DESC,result_status,race_status
LIMIT 25;

-- 3) Actual JSON keys are field PRESENCE ONLY; never certify official
-- refund boats or absence of an incident based on column names.
WITH one_day AS MATERIALIZED (
  SELECT to_jsonb(rs) AS doc
  FROM boat_data.races r
  JOIN public.v2_results rs ON rs.race_id=r.race_id
  WHERE r.race_date=:'day'::date
    AND r.race_date>=DATE '2025-07-01'
), present AS (
  SELECT key,
         count(*) FILTER (
           WHERE jsonb_typeof(doc->fld.key)<>'null'
         ) AS nonnull_rows
  FROM one_day
  CROSS JOIN LATERAL jsonb_object_keys(doc) AS fld(key)
  WHERE fld.key ~* 'refund|return|cancel|void|invalid|incident|status|raw'
  GROUP BY key
)
SELECT key,nonnull_rows
FROM present
ORDER BY key
LIMIT 30;

COMMIT;
SELECT 'V5_REFUND_EVIDENCE_SCHEMA_ONLY_READONLY_NO_FIT_NO_BUY' AS audit;
