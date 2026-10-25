-- V5 fast-start gate: can the already-copied physical stage supply TODAY's input?
-- Read-only / no new collector / no model / no BUY / no route cutover.
-- Compare against existing 13 VIEWs which still point to legacy public tables.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL TIME ZONE 'Asia/Tokyo';
SET LOCAL statement_timeout='15000ms';
SET LOCAL lock_timeout='1000ms';
WITH today AS (SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Tokyo')::date AS d),
names(dest) AS (
 VALUES ('venues'),('races'),('entries'),('results'),('racer_results'),
 ('trifecta_odds'),('racer_course_stats_snapshots'),('entry_snapshots'),
 ('exhibition_snapshots'),('odds_snapshots'),('weather_snapshots'),
 ('race_condition_snapshots'),('racer_condition_snapshots')
), shapes AS (
 SELECT dest,
   (SELECT relkind::text FROM pg_class WHERE oid=to_regclass('boat_data.'||dest)) AS live_kind,
   (SELECT relkind::text FROM pg_class WHERE oid=to_regclass('boat_data_stage.'||dest)) AS stage_kind
 FROM names
)
SELECT 'ROUTE' AS section,dest AS name,
       CASE WHEN live_kind='v' AND stage_kind='r' THEN 'PASS_VIEW_AND_PHYSICAL_STAGE'
            ELSE 'HOLD_RELATION_DRIFT' END AS status
FROM shapes ORDER BY name;

WITH recent_races AS MATERIALIZED (
  SELECT r.race_id
  FROM boat_data.races r
  WHERE r.race_date=(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Tokyo')::date
), stage_races AS MATERIALIZED (
  SELECT r.race_id
  FROM boat_data_stage.races r
  WHERE r.race_date=(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Tokyo')::date
)
SELECT 'TODAY_RACES' AS section,
  (SELECT count(*) FROM recent_races) AS live_original,
  (SELECT count(*) FROM stage_races) AS v5_stage,
  (SELECT count(*) FROM recent_races r
    WHERE NOT EXISTS(SELECT 1 FROM stage_races s WHERE s.race_id=r.race_id))
    AS missing_in_stage,
  CASE WHEN (SELECT count(*) FROM recent_races) =
                 (SELECT count(*) FROM stage_races)
      AND NOT EXISTS (SELECT 1 FROM recent_races r
         WHERE NOT EXISTS (SELECT 1 FROM stage_races s WHERE s.race_id=r.race_id))
    THEN 'STAGE_RACE_IDS_MATCH_NOW'
    ELSE 'STAGE_STALE_USE_LIVE_VIEWS_FOR_PAPER_UNTIL_SYNC'
  END AS verdict;

ROLLBACK;
SELECT 'V5_SHADOW_FRESHNESS_READONLY_DONE_NO_COLLECTION_PAUSE_NO_CUTOVER_NO_BUY' AS verdict;
