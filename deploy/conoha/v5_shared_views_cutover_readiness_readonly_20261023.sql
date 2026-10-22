-- Read-only V5/V6 common-view audit, explicitly NOT a production cutover.
-- Never execute old boat_shared_bulk_schedule_once_20261023.sh after these
-- views exist: bulk staging expects physical targets and will STOP.
-- Zero user-data scans; catalog only, no services or timers modified.
\set ON_ERROR_STOP on
\pset pager off
BEGIN TRANSACTION READ ONLY;
SET LOCAL lock_timeout='1000ms';
SET LOCAL statement_timeout='10000ms';

WITH expected(alias, source) AS (VALUES
  ('venues', 'v2_venues'),
  ('races', 'v2_races'),
  ('entries', 'v2_race_entries'),
  ('results', 'v2_results'),
  ('racer_results', 'v2_result_entries'),
  ('trifecta_odds', 'v2_odds_trifecta'),
  ('racer_course_stats_snapshots', 'v2_racer_course_stats_snapshots'),
  ('entry_snapshots', 'v2_realtime_entry_snapshots'),
  ('exhibition_snapshots', 'v2_realtime_exhibition_snapshots'),
  ('odds_snapshots', 'v2_realtime_odds_snapshots'),
  ('weather_snapshots', 'v2_realtime_weather_snapshots'),
  ('race_condition_snapshots', 'v2_realtime_race_condition_snapshots'),
  ('racer_condition_snapshots', 'v2_realtime_racer_condition_snapshots')
), inventory AS (
  SELECT e.alias, e.source,
         to_regclass(format('boat_data.%I',e.alias)) AS dest_oid,
         to_regclass(format('public.%I',e.source)) AS src_oid
  FROM expected e
)
SELECT 'V5_SHARED_VIEW_CATALOG' AS audit,
       alias, source, dest_oid::text AS destination,
       c.relkind AS destination_kind,
       sc.relkind AS source_kind,
       CASE WHEN c.oid IS NULL THEN NULL
            ELSE pg_relation_is_updatable(c.oid, false) END AS updatable_mask,
       EXISTS(
         SELECT 1 FROM pg_rewrite rw
         JOIN pg_depend d ON d.objid=rw.oid
           AND d.classid='pg_rewrite'::regclass
         WHERE rw.ev_class=c.oid AND rw.rulename='_RETURN'
           AND d.refobjid=sc.oid
       ) AS source_dependency_found
FROM inventory i
LEFT JOIN pg_class c ON c.oid=i.dest_oid
LEFT JOIN pg_class sc ON sc.oid=i.src_oid
ORDER BY alias;

DO $audit$
DECLARE
  item record;
  kind "char";
  src_kind "char";
  mask integer;
  dep_ok boolean;
  n integer:=0;
BEGIN
 IF current_database() <> 'railway'
    OR to_regnamespace('boat_data') IS NULL THEN
   RAISE EXCEPTION 'STOP: wrong DB or common schema missing';
 END IF;
 FOR item IN
   SELECT * FROM (VALUES
  ('venues', 'v2_venues'),
  ('races', 'v2_races'),
  ('entries', 'v2_race_entries'),
  ('results', 'v2_results'),
  ('racer_results', 'v2_result_entries'),
  ('trifecta_odds', 'v2_odds_trifecta'),
  ('racer_course_stats_snapshots', 'v2_racer_course_stats_snapshots'),
  ('entry_snapshots', 'v2_realtime_entry_snapshots'),
  ('exhibition_snapshots', 'v2_realtime_exhibition_snapshots'),
  ('odds_snapshots', 'v2_realtime_odds_snapshots'),
  ('weather_snapshots', 'v2_realtime_weather_snapshots'),
  ('race_condition_snapshots', 'v2_realtime_race_condition_snapshots'),
  ('racer_condition_snapshots', 'v2_realtime_racer_condition_snapshots')
   ) AS e(alias,source)
 LOOP
   SELECT c.relkind, pg_relation_is_updatable(c.oid,false)
     INTO kind,mask
     FROM pg_class c WHERE c.oid=to_regclass(format('boat_data.%I',item.alias));
   SELECT c.relkind INTO src_kind FROM pg_class c
     WHERE c.oid=to_regclass(format('public.%I',item.source));
   SELECT EXISTS(
      SELECT 1 FROM pg_rewrite rw JOIN pg_depend d ON d.objid=rw.oid
      WHERE rw.ev_class=to_regclass(format('boat_data.%I',item.alias))
        AND rw.rulename='_RETURN'
        AND d.classid='pg_rewrite'::regclass
        AND d.refobjid=to_regclass(format('public.%I',item.source))
   ) INTO dep_ok;
   IF kind IS DISTINCT FROM 'v' OR mask IS DISTINCT FROM 0
      OR src_kind NOT IN ('r','p') OR NOT dep_ok THEN
     RAISE EXCEPTION 'STOP: common view contract failed: %, kind %, source kind %, updatable %, dependency %',
        item.alias,kind,src_kind,mask,dep_ok;
   END IF;
   n:=n+1;
 END LOOP;
 IF n<>13 THEN RAISE EXCEPTION 'STOP: expected 13 views, found %',n; END IF;
 RAISE NOTICE 'SHARED_VIEWS_VERIFIED=13 NON_UPDATABLE=13 SOURCE_DEPENDENCIES=13';
END
$audit$;

-- Source and read-only common-schema object types, no data scanned.
SELECT 'BOAT_DATA_RELATION_TYPES' AS audit, c.relkind AS kind, count(*) AS total
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='boat_data' AND c.relkind IN ('r','p','v','m')
GROUP BY c.relkind ORDER BY c.relkind;

COMMIT;
SELECT 'V5_SHARED_VIEWS_READONLY_GATE_PASS_NOT_PHYSICAL_NOT_ENGINE_CUTOVER' AS verdict;
