-- V5 physical consolidation: ONE PASS for 13 canonical sources.
-- Metadata only. NO source row scans, writes, staging, migration or cutover.
-- All current boat_data views / legacy writer paths remain untouched.
\set ON_ERROR_STOP on
\pset pager off
BEGIN TRANSACTION READ ONLY;
SET LOCAL lock_timeout='1500ms';
SET LOCAL statement_timeout='10000ms';
SET LOCAL work_mem='8MB';

WITH planned(family,source_relation,physical_candidate) AS (
 VALUES
 ('master','public.v2_venues','v5_data.venues'),
 ('core','public.v2_races','v5_data.raw_races'),
 ('core','public.v2_race_entries','v5_data.raw_entries'),
 ('results','public.v2_results','v5_data.raw_results'),
 ('results','public.v2_result_entries','v5_data.raw_racer_results'),
 ('odds','public.v2_odds_trifecta','v5_data.trifecta_odds'),
 ('feature','public.v2_racer_course_stats_snapshots','v5_data.raw_racer_course_stats_snapshots'),
 ('realtime','public.v2_realtime_entry_snapshots','v5_data.raw_entry_snapshots'),
 ('realtime','public.v2_realtime_exhibition_snapshots','v5_data.raw_exhibition_snapshots'),
 ('realtime','public.v2_realtime_odds_snapshots','v5_data.raw_odds_snapshots'),
 ('realtime','public.v2_realtime_weather_snapshots','v5_data.raw_weather_snapshots'),
 ('realtime','public.v2_realtime_race_condition_snapshots','v5_data.raw_race_condition_snapshots'),
 ('realtime','public.v2_realtime_racer_condition_snapshots','v5_data.raw_racer_condition_snapshots')
), resolved AS (
 SELECT *,to_regclass(source_relation) AS src,
          to_regclass(physical_candidate) AS dst
 FROM planned
)
SELECT 'V5_13_SOURCE_BATCH_GATE' AS audit,
       r.family,r.source_relation,
       coalesce(src.relkind::text,'MISSING') AS source_kind,
       CASE WHEN r.src IS NULL THEN '-' ELSE pg_size_pretty(pg_total_relation_size(r.src)) END AS source_size_with_indexes,
       r.physical_candidate,
       coalesce(dst.relkind::text,'ABSENT') AS physical_candidate_kind,
       (SELECT count(*) FROM pg_index x
        WHERE x.indrelid=r.src AND x.indisunique) AS source_unique_indexes,
       (SELECT count(*) FROM pg_constraint c
        WHERE c.conrelid=r.src AND c.contype='f') AS source_outbound_fk,
       (SELECT count(*) FROM pg_trigger t
        WHERE t.tgrelid=r.src AND NOT t.tgisinternal) AS user_triggers
FROM resolved r
LEFT JOIN pg_class src ON src.oid=r.src
LEFT JOIN pg_class dst ON dst.oid=r.dst
ORDER BY r.family,r.source_relation;

SELECT 'V5_13_STAGE_AND_CAPACITY' AS audit,
       current_database() AS database,
       pg_size_pretty(pg_database_size(current_database())) AS database_size,
       coalesce((SELECT relkind::text FROM pg_class
                 WHERE oid=to_regclass('boat_data_stage.venues')),'ABSENT') AS venues_stage_kind,
       coalesce((SELECT relkind::text FROM pg_class
                 WHERE oid=to_regclass('boat_data.venues')),'ABSENT') AS live_venues_kind;
ROLLBACK;
SELECT 'V5_13_SOURCE_BATCH_GATE_READONLY_DONE_NO_COPY' AS verdict;
