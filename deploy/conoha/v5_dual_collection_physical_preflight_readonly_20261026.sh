#!/usr/bin/env bash
# V5 physical separation preflight. STRICT READ-ONLY, pg_catalog ONLY.
# No collector runs, HTTP requests, service edits, timer changes, DDL, DML, BUY.
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "HOLD_RUN_AS_ROOT_FOR_LOCAL_POSTGRES_PEER_AUTH"; exit 2
fi
if ! command -v runuser >/dev/null || ! command -v psql >/dev/null; then
  echo "HOLD_LOCAL_POSTGRES_CLIENT_MISSING"; exit 2
fi
echo "V5_DUAL_WRITER_PHYSICAL_PREFLIGHT_BEGIN_NO_LIVE_CHANGES"
runuser -u postgres -- psql -X -v ON_ERROR_STOP=1 -d railway -P pager=off -A -F '|' <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='500ms';
SET LOCAL work_mem='4MB';
\echo PHYSICAL_STAGE_13_FAMILY_CATALOG
WITH m(src,dst,expected_key) AS (VALUES
 ('public.v2_venues','boat_data_stage.venues',''),
 ('public.v2_races','boat_data_stage.races',''),
 ('public.v2_race_entries','boat_data_stage.entries',''),
 ('public.v2_results','boat_data_stage.results',''),
 ('public.v2_result_entries','boat_data_stage.racer_results',''),
 ('public.v2_odds_trifecta','boat_data_stage.trifecta_odds',''),
 ('public.v2_racer_course_stats_snapshots','boat_data_stage.racer_course_stats_snapshots',''),
 ('public.v2_realtime_entry_snapshots','boat_data_stage.entry_snapshots','race_id,snapshot_label,lane'),
 ('public.v2_realtime_exhibition_snapshots','boat_data_stage.exhibition_snapshots','race_id,snapshot_label,lane'),
 ('public.v2_realtime_odds_snapshots','boat_data_stage.odds_snapshots','race_id,snapshot_label,ticket'),
 ('public.v2_realtime_weather_snapshots','boat_data_stage.weather_snapshots','race_id,snapshot_label'),
 ('public.v2_realtime_race_condition_snapshots','boat_data_stage.race_condition_snapshots','race_id,snapshot_label'),
 ('public.v2_realtime_racer_condition_snapshots','boat_data_stage.racer_condition_snapshots','race_id,snapshot_label,lane')
), x AS (
 SELECT m.*,
        to_regclass(m.src) AS src_oid, to_regclass(m.dst) AS dst_oid
 FROM m
), audited AS (
 SELECT x.*,
    (SELECT c.relkind FROM pg_class c WHERE c.oid=x.src_oid) AS src_kind,
    (SELECT c.relkind FROM pg_class c WHERE c.oid=x.dst_oid) AS dst_kind,
    (SELECT count(*) FROM pg_attribute a
       WHERE a.attrelid=x.src_oid AND a.attnum>0 AND NOT a.attisdropped
         AND a.attname<>'id' AND NOT EXISTS (
           SELECT 1 FROM pg_attribute b
           WHERE b.attrelid=x.dst_oid AND b.attnum>0
             AND NOT b.attisdropped AND b.attname=a.attname
         )) AS legacy_columns_not_in_stage,
    (SELECT count(*) FROM pg_trigger t
       WHERE t.tgrelid=x.dst_oid AND NOT t.tgisinternal) AS stage_user_triggers,
    (SELECT count(*) FROM pg_index i
       WHERE i.indrelid=x.dst_oid AND i.indisunique AND i.indisvalid
         AND i.indpred IS NULL AND i.indexprs IS NULL
         AND (SELECT string_agg(a.attname, ',' ORDER BY z.ord)
              FROM unnest(i.indkey) WITH ORDINALITY z(attnum,ord)
              JOIN pg_attribute a ON a.attrelid=i.indrelid
                                AND a.attnum=z.attnum
              WHERE z.ord<=i.indnkeyatts)=x.expected_key) AS expected_unique_keys
 FROM x
)
SELECT src, dst, coalesce(src_kind::text,'ABSENT') AS source_kind,
       coalesce(dst_kind::text,'ABSENT') AS target_kind,
       legacy_columns_not_in_stage AS source_columns_missing_stage_excluding_id,
       stage_user_triggers,
       CASE WHEN expected_key='' THEN 'CHECK_SEPARATELY'
            WHEN expected_unique_keys>0 THEN 'KEY_OK' ELSE 'HOLD_UNIQUE_KEY' END AS snapshot_key,
       CASE WHEN src_kind NOT IN ('r','p') OR src_kind IS NULL
                      OR dst_kind NOT IN ('r','p') OR dst_kind IS NULL
                 THEN 'HOLD_NOT_SEPARATE_PHYSICAL_TABLES'
            WHEN expected_key<>'' AND expected_unique_keys=0
                 THEN 'HOLD_SNAPSHOT_UNIQUE_KEY'
            ELSE 'CATALOG_ONLY_NOT_WRITER_APPROVAL' END AS verdict
FROM audited ORDER BY src;
\echo BOAT_DATA_CANONICAL_VIEW_STATUS
SELECT n.nspname||'.'||c.relname AS relation,c.relkind
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='boat_data' AND c.relname IN
   ('races','entries','entry_snapshots','exhibition_snapshots','odds_snapshots',
    'weather_snapshots','results') ORDER BY c.relname;
ROLLBACK;
SQL
echo "=== RELEVANT TIMERS (READ ONLY) ==="
systemctl list-timers --all --no-pager --no-legend 2>/dev/null |
  grep -E 'boat-v5-(forward-window|stage11-delta-20261027-recovery|daily@|midnight-catchup)' || true
echo "V5_DUAL_WRITER_PHYSICAL_PREFLIGHT_COMPLETE_NO_DB_WRITES_NO_SWITCH_NO_BUY"
