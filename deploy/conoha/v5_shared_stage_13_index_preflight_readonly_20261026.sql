-- Shared V5 data ONLY: index/date readiness before bounded 2025-07+ period scans.
-- Catalog-only: never reads any user table's rows; no legacy data checks.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN READ ONLY;
SET LOCAL statement_timeout = '4s';
SET LOCAL lock_timeout = '500ms';
WITH family(name, is_master) AS (
  VALUES
  ('venues',true),('races',false),('entries',false),
  ('results',false),('racer_results',false),('trifecta_odds',false),
  ('racer_course_stats_snapshots',false),('entry_snapshots',false),
  ('exhibition_snapshots',false),('odds_snapshots',false),
  ('weather_snapshots',false),('race_condition_snapshots',false),
  ('racer_condition_snapshots',false)
), objects AS (
  SELECT name,is_master,to_regclass('boat_data_stage.'||name) oid
  FROM family
), index_info AS (
  SELECT o.name,
         string_agg(DISTINCT a.attname,',' ORDER BY a.attname) FILTER
           (WHERE a.attname IS NOT NULL) AS leading_keys,
         bool_or(a.attname IN ('race_date','snapshot_date','captured_at','snapshot_at','fetched_at')) AS direct_date_index,
         bool_or(a.attname = 'race_id') AS race_id_index
  FROM objects o
  LEFT JOIN pg_index i ON i.indrelid=o.oid AND i.indisvalid AND i.indisready
  LEFT JOIN pg_attribute a ON a.attrelid=o.oid AND a.attnum=i.indkey[0] AND a.attnum>0
  GROUP BY o.name
), time_info AS (
  SELECT o.name,
         string_agg(a.attname||':'||format_type(a.atttypid,a.atttypmod),',' ORDER BY a.attnum)
           FILTER (WHERE a.attname IS NOT NULL) AS time_columns
  FROM objects o
  LEFT JOIN pg_attribute a ON a.attrelid=o.oid AND a.attnum>0
    AND NOT a.attisdropped
    AND (a.attname IN ('race_id','race_date','snapshot_date','captured_at','snapshot_at','fetched_at')
      OR a.attname LIKE '%_at')
  GROUP BY o.name
)
SELECT o.name AS shared_family,
       CASE
         WHEN c.relkind IS DISTINCT FROM 'r' THEN 'HOLD_NOT_PHYSICAL_STAGE'
         WHEN o.is_master THEN 'MASTER_NOT_MONTHLY_RACE_DATA'
         WHEN coalesce(i.direct_date_index,false) THEN 'CANDIDATE_INDEXED_TIME_CHECK_SEMANTICS'
         WHEN coalesce(i.race_id_index,false) THEN 'CANDIDATE_RACE_ID_CHECK_FORMAT_SEMANTICS'
         ELSE 'HOLD_NO_SAFE_PERIOD_INDEX_PROVEN'
       END AS next_monthly_scan_gate,
       coalesce(i.leading_keys,'NONE') AS index_first_keys,
       coalesce(t.time_columns,'NO_CANDIDATE_TIME_COLUMN') AS candidate_time_columns,
       coalesce(pg_size_pretty(pg_total_relation_size(o.oid)),'-') AS stage_size
FROM objects o
LEFT JOIN pg_class c ON c.oid=o.oid
LEFT JOIN index_info i ON i.name=o.name
LEFT JOIN time_info t ON t.name=o.name
ORDER BY o.name;
ROLLBACK;
\echo V5_SHARED_13_INDEX_PREFLIGHT_COMPLETE_READ_ONLY_CATALOG_ONLY_NO_MONTHLY_SCAN_BUY_OFF
