-- Confirm all 13 stage relations physically exist and the 12 new snapshots
-- have the copier's completion metadata. Fast PG catalog-only, NO TABLE SCANS,
-- NO CREATE/INSERT/ALTER, NO live switch. Initial parity / CDC NOT proven.
\set ON_ERROR_STOP on
\pset pager off
\pset format aligned
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '1s';
WITH routes(source_name, target_name) AS (
 VALUES
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
), relations AS (
 SELECT source_name,target_name,
        to_regclass('public.' || source_name) AS source_oid,
        to_regclass('boat_data.' || target_name) AS view_oid,
        to_regclass('boat_data_stage.' || target_name) AS stage_oid
 FROM routes
), evaluated AS (
 SELECT r.*, src.relkind AS source_kind,
        v.relkind AS live_kind,
        st.relkind AS stage_kind,
        pg_total_relation_size(r.stage_oid) AS stage_bytes,
        obj_description(r.stage_oid, 'pg_class') AS note
 FROM relations r
 LEFT JOIN pg_class src ON src.oid=r.source_oid
 LEFT JOIN pg_class v ON v.oid=r.view_oid
 LEFT JOIN pg_class st ON st.oid=r.stage_oid
)
SELECT target_name,
       coalesce(source_kind::text,'MISSING') AS source_kind,
       coalesce(live_kind::text,'MISSING') AS live_kind,
       coalesce(stage_kind::text,'MISSING') AS stage_kind,
       CASE
        WHEN source_kind<>'r' OR live_kind<>'v' OR stage_kind<>'r'
         THEN 'HOLD_RELATION_MISMATCH'
        WHEN target_name='venues'
         THEN 'PREVIOUS_VENUES_STAGE_PRESENT'
        WHEN note LIKE 'BOAT_V5_STAGE_ONLY_SNAPSHOT_20261025 source=public.' || source_name || ' %'
         THEN 'INITIAL_SNAPSHOT_COMMITTED'
        ELSE 'HOLD_MISSING_COPY_PROOF'
       END AS stage_proof,
       pg_size_pretty(stage_bytes) AS stage_disk,
       left(coalesce(note,''),160) AS completion_note
FROM evaluated ORDER BY target_name;
ROLLBACK;
SELECT 'V5_STAGE13_CATALOG_AUDIT_DONE_READ_ONLY_NO_CDC_NO_CUTOVER' AS verdict;
