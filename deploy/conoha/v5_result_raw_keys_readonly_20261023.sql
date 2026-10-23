-- V5 research evidence discovery: nested result JSON KEY NAMES, not values.
-- One day only. Does NOT establish refund absence, incident-free proof,
-- source authenticity, original capture, research-fit or Forward eligibility.
-- Do not promote any 'official' status or missing key to refund_boats=().
-- No SQL writes / schema changes / results replay / HTTP / BUY.
-- Usage: psql -v day=2026-10-20 -f /tmp/v5_raw_keys.sql
\set ON_ERROR_STOP on
\pset pager off
\if :{?day}
\else
\set day 2026-10-20
\endif
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='12000ms';
SET LOCAL lock_timeout='1000ms';
SET LOCAL work_mem='8MB';

WITH day_results AS MATERIALIZED (
  SELECT rs.race_id,rs.raw
  FROM public.v2_results rs
  JOIN boat_data.races r ON r.race_id=rs.race_id
  WHERE r.race_date=:'day'::date AND r.race_date>=DATE '2025-07-01'
)
SELECT :'day'::date AS inspected_day,
       coalesce(jsonb_typeof(raw),'SQL_NULL') AS raw_type,
       count(*)::integer AS result_rows
FROM day_results
GROUP BY 1,2
ORDER BY raw_type;

WITH day_results AS MATERIALIZED (
  SELECT rs.race_id,rs.raw
  FROM public.v2_results rs
  JOIN boat_data.races r ON r.race_id=rs.race_id
  WHERE r.race_date=:'day'::date AND r.race_date>=DATE '2025-07-01'
), raw_keys AS (
  SELECT d.race_id,kv.key,
         jsonb_typeof(kv.value) AS value_type
  FROM day_results d
  CROSS JOIN LATERAL jsonb_each(
    CASE WHEN jsonb_typeof(d.raw)='object'
         THEN d.raw ELSE '{}'::jsonb END
  ) AS kv(key,value)
)
SELECT key,value_type,
       count(DISTINCT race_id)::integer AS races_with_key
FROM raw_keys
GROUP BY key,value_type
ORDER BY races_with_key DESC,key,value_type
LIMIT 35;

-- One nested object level. Do not print the JSON values or raw HTML.
WITH day_results AS MATERIALIZED (
  SELECT rs.race_id,rs.raw
  FROM public.v2_results rs
  JOIN boat_data.races r ON r.race_id=rs.race_id
  WHERE r.race_date=:'day'::date AND r.race_date>=DATE '2025-07-01'
), nested_keys AS (
  SELECT d.race_id,outer_kv.key AS parent_key,
         inner_kv.key AS child_key,
         jsonb_typeof(inner_kv.value) AS value_type
  FROM day_results d
  CROSS JOIN LATERAL jsonb_each(
    CASE WHEN jsonb_typeof(d.raw)='object'
         THEN d.raw ELSE '{}'::jsonb END
  ) AS outer_kv(key,value)
  CROSS JOIN LATERAL jsonb_each(
    CASE WHEN jsonb_typeof(outer_kv.value)='object'
         THEN outer_kv.value ELSE '{}'::jsonb END
  ) AS inner_kv(key,value)
)
SELECT parent_key,child_key,value_type,
       count(DISTINCT race_id)::integer AS races_with_nested_key
FROM nested_keys
GROUP BY parent_key,child_key,value_type
ORDER BY races_with_nested_key DESC,parent_key,child_key
LIMIT 35;

COMMIT;
SELECT 'V5_RAW_KEY_NAMES_ONLY_READONLY_REFUND_UNVERIFIED_NO_FIT_NO_BUY' AS audit;
