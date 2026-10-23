-- Bounded V5 exhibition storage-gap triage, READ ONLY.
-- Prior confirmed 2026-10-10/15/17/18/19 have no 6-lane records in
-- boat_data.exhibition_snapshots. This SQL does NOT claim no data exists.
-- 1) Inspect schemas of likely alternative sources without reading their rows.
-- 2) Count matching races in public.v2_exhibition for exactly 5 dates.
-- 3) Group 2026-10-01/05 snapshot labels to explain pre-gap label changes.
-- Neither rows nor mutable capture timestamps prove historical first access.
-- No DB writes, external DB/HTTP, recapture, model training or BUY.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='15000ms';
SET LOCAL lock_timeout='1000ms';
SET LOCAL work_mem='8MB';

SELECT table_schema||'.'||table_name AS relation,
       string_agg(column_name||':'||data_type, ', ' ORDER BY ordinal_position)
         AS observed_columns
FROM information_schema.columns
WHERE table_schema='public'
  AND table_name IN (
    'v2_exhibition',
    'v2_bao_exhibition_shadow_snapshots',
    'v2_exhibition_shadow_decisions',
    'v2_exhibition_shadow_results',
    'v2_exhibition_st_forward_shadow',
    'v4_exhibition_quarantine_20261017',
    'v2_realtime_exhibition_snapshots'
  )
  AND column_name ~* (
    'race_id|race_date|lane|exhibit|rank|snapshot|'
    ||'capture|fetched|created|source|raw|label|status'
  )
GROUP BY table_schema,table_name
ORDER BY relation;

WITH target(day) AS (
 VALUES
 (DATE '2026-10-10'),
 (DATE '2026-10-15'),
 (DATE '2026-10-17'),
 (DATE '2026-10-18'),
 (DATE '2026-10-19')
), races AS MATERIALIZED (
 SELECT r.race_id,r.race_date
 FROM boat_data.races r
 JOIN target t ON t.day=r.race_date
), older AS MATERIALIZED (
 SELECT r.race_date,e.race_id
 FROM races r
 JOIN public.v2_exhibition e ON e.race_id=r.race_id
)
SELECT to_char(t.day,'YYYY-MM-DD') AS day,
       (SELECT count(*) FROM races r WHERE r.race_date=t.day) AS known_races,
       count(o.race_id)::integer AS old_exhibition_rows_not_verified,
       count(DISTINCT o.race_id)::integer AS old_exhibition_races_not_verified
FROM target t LEFT JOIN older o ON o.race_date=t.day
GROUP BY t.day
ORDER BY t.day;

WITH r AS MATERIALIZED (
 SELECT race_id,race_date
 FROM boat_data.races
 WHERE race_date IN (DATE '2026-10-01',DATE '2026-10-05')
), labels AS MATERIALIZED (
 SELECT r.race_date,x.snapshot_label,x.race_id,
        count(*)::int AS boat_rows,
        count(DISTINCT x.lane) FILTER (
          WHERE x.lane BETWEEN 1 AND 6
            AND x.exhibition_time_rank BETWEEN 1 AND 6
        )::int AS valid_lanes,
        count(DISTINCT x.exhibition_time_rank) FILTER (
          WHERE x.lane BETWEEN 1 AND 6
            AND x.exhibition_time_rank BETWEEN 1 AND 6
        )::int AS valid_ranks
 FROM r
 JOIN boat_data.exhibition_snapshots x USING(race_id)
 GROUP BY r.race_date,x.snapshot_label,x.race_id
)
SELECT to_char(race_date,'YYYY-MM-DD') AS day,
       CASE
         WHEN snapshot_label='historical' THEN 'historical'
         WHEN snapshot_label LIKE 'conoha_forward_%' THEN 'conoha_forward_*'
         WHEN snapshot_label LIKE 'conoha_%' THEN 'conoha_other_*'
         WHEN snapshot_label IS NULL THEN '(NULL)'
         ELSE left(snapshot_label,48)
       END AS label_family,
       count(DISTINCT race_id)::int AS races_with_rows,
       count(DISTINCT race_id) FILTER (
         WHERE boat_rows=6 AND valid_lanes=6 AND valid_ranks=6
       )::int AS complete_six_races_NOT_PROOF
FROM labels
GROUP BY race_date,label_family
ORDER BY race_date,label_family
LIMIT 24;

COMMIT;
SELECT 'V5_EXHIBITION_ALT_SOURCE_5_DAYS_READONLY_NO_FIRST_WRITE_PROOF_NO_BUY' AS audit;
