-- V5 logical storage schema stage 2: candidate environmental inputs vs shadow research.
-- Applies ONLY after v5_data_views_v1.sql succeeded on ConoHa local database 'railway'.
-- No raw data copied/deleted; no source table DML; no existing collector/timer changes.
-- OFFSET 0 makes aliases non-auto-updatable (matches stage 1). Be alert that
-- this layer is a storage classification, NOT proven prediction-time safety.
-- The old V24 motor2 shadow output MUST NEVER become V5 production motor stats.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '20s';

DO $$
BEGIN
 IF to_regnamespace('v5_data') IS NULL
    OR to_regclass('v5_data.races') IS NULL
    OR to_regclass('v5_data.results') IS NULL THEN
    RAISE EXCEPTION 'v5_data v1 prerequisites absent. Apply/check stage 1 first.';
 END IF;
END
$$;

CREATE VIEW v5_data.weather_snapshots AS
SELECT * FROM public.v2_realtime_weather_snapshots OFFSET 0;
COMMENT ON VIEW v5_data.weather_snapshots IS
  'Historical weather capture; source and snapshot_at require predeadline eligibility audit. No proven first observation.';

CREATE VIEW v5_data.race_condition_snapshots AS
SELECT * FROM public.v2_realtime_race_condition_snapshots OFFSET 0;
COMMENT ON VIEW v5_data.race_condition_snapshots IS
  'Historical preinformation/race-condition snapshots. Source timestamp and six-lane completeness require separate audit.';

CREATE VIEW v5_data.racer_condition_snapshots AS
SELECT * FROM public.v2_realtime_racer_condition_snapshots OFFSET 0;
COMMENT ON VIEW v5_data.racer_condition_snapshots IS
  'Historical per-lane racer-condition snapshots. Do not assume this was seen before the actual race deadline.';

CREATE VIEW v5_data.racer_course_stats_snapshots AS
SELECT * FROM public.v2_racer_course_stats_snapshots OFFSET 0;
COMMENT ON VIEW v5_data.racer_course_stats_snapshots IS
  'Racer-course statistical snapshots: snapshot_date and created_at do not alone certify as-of provenance.';

CREATE SCHEMA v5_research;
COMMENT ON SCHEMA v5_research IS
  'Separate legacy and experimental study data; no live V5 input, BUY permission, or realized ROI claim.';

CREATE VIEW v5_research.motor2_legacy_shadow AS
SELECT * FROM public.v2_v24_motor2_forward_shadow OFFSET 0;
COMMENT ON VIEW v5_research.motor2_legacy_shadow IS
  'Legacy V24 motor2 forward shadow only: does NOT constitute validated V5 motor_stats, prediction, or purchase evidence.';

REVOKE ALL ON TABLE
  v5_data.weather_snapshots,
  v5_data.race_condition_snapshots,
  v5_data.racer_condition_snapshots,
  v5_data.racer_course_stats_snapshots
FROM PUBLIC;
REVOKE ALL ON SCHEMA v5_research FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA v5_research FROM PUBLIC;

COMMIT;

SELECT table_schema, table_name, is_updatable
FROM information_schema.views
WHERE (table_schema='v5_data'
   AND table_name IN ('weather_snapshots','race_condition_snapshots',
      'racer_condition_snapshots','racer_course_stats_snapshots'))
   OR (table_schema='v5_research' AND table_name='motor2_legacy_shadow')
ORDER BY table_schema, table_name;

SELECT n.nspname AS schema_name,
 COUNT(*) FILTER (WHERE c.relkind='v') AS view_count
FROM pg_namespace n
JOIN pg_class c ON n.oid=c.relnamespace
WHERE n.nspname IN ('v5_data', 'v5_research')
GROUP BY n.nspname
ORDER BY n.nspname;
