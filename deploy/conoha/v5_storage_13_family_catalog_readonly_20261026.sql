-- V5 13-family storage contract: catalog-only, no user table scans, writes or cutover.
-- Inspects physical legacy source, protected logical view, and physical stage.
-- Schema equality is not proof of period coverage or original as-of provenance.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN READ ONLY;
SET LOCAL statement_timeout = '4s';
SET LOCAL lock_timeout = '500ms';
WITH routes(source_name, target_name, evidence_rule) AS (
 VALUES
 ('v2_venues','venues','MASTER_VERSION'),
 ('v2_races','races','RACE_CUTOFF'),
 ('v2_race_entries','entries','RACER_ASOF'),
 ('v2_results','results','POSTRACE_ONLY'),
 ('v2_result_entries','racer_results','POSTRACE_ONLY'),
 ('v2_odds_trifecta','trifecta_odds','ODDS_ASOF_REQUIRED'),
 ('v2_racer_course_stats_snapshots','racer_course_stats_snapshots','ASOF_REQUIRED'),
 ('v2_realtime_entry_snapshots','entry_snapshots','PREDEADLINE_CAPTURE'),
 ('v2_realtime_exhibition_snapshots','exhibition_snapshots','PREDEADLINE_CAPTURE'),
 ('v2_realtime_odds_snapshots','odds_snapshots','PREDEADLINE_CAPTURE'),
 ('v2_realtime_weather_snapshots','weather_snapshots','PREDEADLINE_CAPTURE'),
 ('v2_realtime_race_condition_snapshots','race_condition_snapshots','PREDEADLINE_CAPTURE'),
 ('v2_realtime_racer_condition_snapshots','racer_condition_snapshots','PREDEADLINE_CAPTURE')
), oids AS (
 SELECT r.*,
        to_regclass('public.'||source_name) src_oid,
        to_regclass('boat_data.'||target_name) live_oid,
        to_regclass('boat_data_stage.'||target_name) stage_oid
 FROM routes r
), profiles AS (
 SELECT o.*, s.relkind source_kind, l.relkind live_kind, t.relkind stage_kind,
        (SELECT jsonb_agg(
          jsonb_build_array(a.attname,a.atttypid::text,a.atttypmod,a.attnotnull,a.attcollation::text)
          ORDER BY a.attnum)
          FROM pg_attribute a WHERE a.attrelid=o.src_oid AND a.attnum>0 AND NOT a.attisdropped) source_shape,
        (SELECT jsonb_agg(
          jsonb_build_array(a.attname,a.atttypid::text,a.atttypmod,a.attnotnull,a.attcollation::text)
          ORDER BY a.attnum)
          FROM pg_attribute a WHERE a.attrelid=o.stage_oid AND a.attnum>0 AND NOT a.attisdropped) stage_shape,
        (SELECT string_agg(a.attname,',' ORDER BY k.ord)
         FROM pg_index i
         JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,ord)
           ON k.ord<=i.indnkeyatts
         JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
         WHERE i.indrelid=o.src_oid AND i.indisprimary) source_pk,
        (SELECT string_agg(a.attname,',' ORDER BY k.ord)
         FROM pg_index i
         JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,ord)
           ON k.ord<=i.indnkeyatts
         JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
         WHERE i.indrelid=o.stage_oid AND i.indisprimary) stage_pk,
        (SELECT string_agg(a.attname||':'||format_type(a.atttypid,a.atttypmod),',' ORDER BY a.attnum)
         FROM pg_attribute a
         WHERE a.attrelid=o.src_oid AND a.attnum>0 AND NOT a.attisdropped
           AND (a.attname='race_id' OR a.attname ~ '(date|time|_at|snapshot|captured)')) time_candidates,
        obj_description(o.stage_oid,'pg_class') stage_note
 FROM oids o
 LEFT JOIN pg_class s ON s.oid=o.src_oid
 LEFT JOIN pg_class l ON l.oid=o.live_oid
 LEFT JOIN pg_class t ON t.oid=o.stage_oid
)
SELECT target_name AS family,
       CASE
         WHEN source_kind IS DISTINCT FROM 'r' OR live_kind IS DISTINCT FROM 'v'
              OR stage_kind IS DISTINCT FROM 'r' THEN 'HOLD_RELATION_ROUTE'
         WHEN source_shape IS DISTINCT FROM stage_shape THEN 'HOLD_COLUMN_SHAPE'
         WHEN source_pk IS NULL OR stage_pk IS DISTINCT FROM source_pk THEN 'HOLD_PRIMARY_KEY'
         WHEN target_name<>'venues' AND
              stage_note NOT LIKE 'BOAT_V5_STAGE_ONLY_SNAPSHOT_20261025 source=public.'||source_name||' %'
              THEN 'HOLD_STAGE_ORIGIN_PROOF'
         ELSE 'CATALOG_SHAPE_OK_PERIOD_NOT_AUDITED'
       END AS catalog_verdict,
       coalesce(source_kind::text,'-') AS src_kind,
       coalesce(live_kind::text,'-') AS view_kind,
       coalesce(stage_kind::text,'-') AS stage_kind,
       coalesce(jsonb_array_length(source_shape),0) AS src_cols,
       coalesce(jsonb_array_length(stage_shape),0) AS stage_cols,
       coalesce(source_pk,'NONE') AS src_pk,
       coalesce(stage_pk,'NONE') AS stage_pk,
       coalesce(time_candidates,'NO_TIMESTAMP_COLUMN') AS date_keys,
       evidence_rule
FROM profiles
ORDER BY target_name;
ROLLBACK;
\echo V5_13_FAMILY_CATALOG_DONE_READ_ONLY_NO_ROW_SCANS_NO_PERIOD_COVERAGE_NO_CUTOVER_BUY_OFF
