-- Fast, storage-neutral exposure of the SAME 13 primary ConoHa physical sources
-- to V5 and later V6 via non-updatable SQL read views.
-- This does NOT copy/move raw data, enable predictions/BUY, or change ANY writer.
-- The public.v2_* names remain authoritative writable physical tables.
-- Materialized/physical cutover and old-table cleanup are separate projects.
-- Requires schema boat_data already created; fails closed on any missing source.
\set ON_ERROR_STOP on
\pset pager off
BEGIN;
SET LOCAL lock_timeout = '1500ms';
SET LOCAL statement_timeout = '30000ms';
DO $$
DECLARE
    source_name text;
    target_name text;
    source_oid oid;
    source_kind "char";
    rec record;
BEGIN
    IF current_database() <> 'railway' THEN
        RAISE EXCEPTION 'STOP: expected railway database';
    END IF;
    IF current_user <> 'postgres' THEN
        RAISE EXCEPTION 'STOP: postgres owner required';
    END IF;
    IF to_regnamespace('boat_data') IS NULL THEN
        RAISE EXCEPTION 'STOP: boat_data namespace not created';
    END IF;
    IF (SELECT count(*) FROM pg_class WHERE relnamespace=to_regnamespace('boat_data')) <> 0 THEN
        RAISE EXCEPTION 'STOP: boat_data already has objects; do NOT rerun or overwrite';
    END IF;
    FOR rec IN
        SELECT src, alias FROM (VALUES
      ('v2_venues','venues'),
      ('v2_races','races'),
      ('v2_race_entries','entries'),
      ('v2_results','results'),
      ('v2_result_entries','racer_results'),
      ('v2_odds_trifecta','trifecta_odds'),
      ('v2_racer_course_stats_snapshots','racer_course_stats_snapshots'),
      ('v2_realtime_entry_snapshots','entry_snapshots'),
      ('v2_realtime_exhibition_snapshots','exhibition_snapshots'),
      ('v2_realtime_odds_snapshots','odds_snapshots'),
      ('v2_realtime_weather_snapshots','weather_snapshots'),
      ('v2_realtime_race_condition_snapshots','race_condition_snapshots'),
      ('v2_realtime_racer_condition_snapshots','racer_condition_snapshots')
        ) AS v(src,alias)
    LOOP
        source_name := 'public.' || rec.src;
        target_name := 'boat_data.' || rec.alias;
        source_oid := to_regclass(source_name);
        IF source_oid IS NULL THEN
            RAISE EXCEPTION 'STOP: required source % absent; no shared views created', source_name;
        END IF;
        SELECT relkind INTO source_kind FROM pg_class WHERE oid=source_oid;
        IF source_kind NOT IN ('r','p') THEN
            RAISE EXCEPTION 'STOP: source % not a physical table', source_name;
        END IF;
        IF to_regclass(target_name) IS NOT NULL THEN
            RAISE EXCEPTION 'STOP: target % already exists', target_name;
        END IF;
    END LOOP;
END $$;

-- OFFSET 0 makes every alias non-auto-updatable in PostgreSQL.
CREATE VIEW boat_data.venues AS SELECT * FROM public.v2_venues OFFSET 0;
COMMENT ON VIEW boat_data.venues IS 'Common V5/V6 READ ONLY alias to public.v2_venues; evidence=MASTER_VERSION; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.venues FROM PUBLIC;

CREATE VIEW boat_data.races AS SELECT * FROM public.v2_races OFFSET 0;
COMMENT ON VIEW boat_data.races IS 'Common V5/V6 READ ONLY alias to public.v2_races; evidence=RACE_CUTOFF; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.races FROM PUBLIC;

CREATE VIEW boat_data.entries AS SELECT * FROM public.v2_race_entries OFFSET 0;
COMMENT ON VIEW boat_data.entries IS 'Common V5/V6 READ ONLY alias to public.v2_race_entries; evidence=RACER_ASOF; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.entries FROM PUBLIC;

CREATE VIEW boat_data.results AS SELECT * FROM public.v2_results OFFSET 0;
COMMENT ON VIEW boat_data.results IS 'Common V5/V6 READ ONLY alias to public.v2_results; evidence=POSTRACE_ONLY; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.results FROM PUBLIC;

CREATE VIEW boat_data.racer_results AS SELECT * FROM public.v2_result_entries OFFSET 0;
COMMENT ON VIEW boat_data.racer_results IS 'Common V5/V6 READ ONLY alias to public.v2_result_entries; evidence=POSTRACE_ONLY; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.racer_results FROM PUBLIC;

CREATE VIEW boat_data.trifecta_odds AS SELECT * FROM public.v2_odds_trifecta OFFSET 0;
COMMENT ON VIEW boat_data.trifecta_odds IS 'Common V5/V6 READ ONLY alias to public.v2_odds_trifecta; evidence=ODDS_ASOF_REQUIRED; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.trifecta_odds FROM PUBLIC;

CREATE VIEW boat_data.racer_course_stats_snapshots AS SELECT * FROM public.v2_racer_course_stats_snapshots OFFSET 0;
COMMENT ON VIEW boat_data.racer_course_stats_snapshots IS 'Common V5/V6 READ ONLY alias to public.v2_racer_course_stats_snapshots; evidence=ASOF_REQUIRED; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.racer_course_stats_snapshots FROM PUBLIC;

CREATE VIEW boat_data.entry_snapshots AS SELECT * FROM public.v2_realtime_entry_snapshots OFFSET 0;
COMMENT ON VIEW boat_data.entry_snapshots IS 'Common V5/V6 READ ONLY alias to public.v2_realtime_entry_snapshots; evidence=PREDEADLINE_CAPTURE; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.entry_snapshots FROM PUBLIC;

CREATE VIEW boat_data.exhibition_snapshots AS SELECT * FROM public.v2_realtime_exhibition_snapshots OFFSET 0;
COMMENT ON VIEW boat_data.exhibition_snapshots IS 'Common V5/V6 READ ONLY alias to public.v2_realtime_exhibition_snapshots; evidence=PREDEADLINE_CAPTURE; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.exhibition_snapshots FROM PUBLIC;

CREATE VIEW boat_data.odds_snapshots AS SELECT * FROM public.v2_realtime_odds_snapshots OFFSET 0;
COMMENT ON VIEW boat_data.odds_snapshots IS 'Common V5/V6 READ ONLY alias to public.v2_realtime_odds_snapshots; evidence=PREDEADLINE_CAPTURE; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.odds_snapshots FROM PUBLIC;

CREATE VIEW boat_data.weather_snapshots AS SELECT * FROM public.v2_realtime_weather_snapshots OFFSET 0;
COMMENT ON VIEW boat_data.weather_snapshots IS 'Common V5/V6 READ ONLY alias to public.v2_realtime_weather_snapshots; evidence=PREDEADLINE_CAPTURE; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.weather_snapshots FROM PUBLIC;

CREATE VIEW boat_data.race_condition_snapshots AS SELECT * FROM public.v2_realtime_race_condition_snapshots OFFSET 0;
COMMENT ON VIEW boat_data.race_condition_snapshots IS 'Common V5/V6 READ ONLY alias to public.v2_realtime_race_condition_snapshots; evidence=PREDEADLINE_CAPTURE; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.race_condition_snapshots FROM PUBLIC;

CREATE VIEW boat_data.racer_condition_snapshots AS SELECT * FROM public.v2_realtime_racer_condition_snapshots OFFSET 0;
COMMENT ON VIEW boat_data.racer_condition_snapshots IS 'Common V5/V6 READ ONLY alias to public.v2_realtime_racer_condition_snapshots; evidence=PREDEADLINE_CAPTURE; original data is not migrated; preserve predeadline/as-of discipline.';
REVOKE ALL ON TABLE boat_data.racer_condition_snapshots FROM PUBLIC;

-- A future route must NOT issue INSERT ... ON CONFLICT to these views.
-- Allowing the default collectors to keep writing original public tables
-- avoids losing the overnight and 01:20 incremental result catch-up.
WITH v AS (
 SELECT c.relname, pg_relation_is_updatable(c.oid, false) AS mask
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='boat_data' AND c.relkind='v'
)
SELECT 'SHARED_READ_VIEWS' AS audit, count(*) AS view_count,
       count(*) FILTER (WHERE mask <> 0) AS unexpectedly_updatable
FROM v;

DO $$
DECLARE
   n_views integer;
   n_update integer;
BEGIN
   SELECT count(*),
          count(*) FILTER (WHERE pg_relation_is_updatable(c.oid, false) <> 0)
     INTO n_views,n_update
   FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='boat_data' AND c.relkind='v';
   IF n_views <> 13 OR n_update <> 0 THEN
       RAISE EXCEPTION 'STOP: shared 13 read-view verification failed';
   END IF;
END $$;
COMMIT;
SELECT 'BOAT_SHARED_THIRTEEN_LIVE_SOURCE_VIEWS_READY_NO_DATA_COPIED_NO_WRITERS_CHANGED' AS verdict;
