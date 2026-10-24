-- V5 13-family stage -> live-source delta readiness, METADATA ONLY.
-- Do NOT interpret this as delta equality, CDC, permission to write, or cutover.
-- No full scans, no DB changes, no timer / BUY / source changes.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='15s';
SET LOCAL lock_timeout='1s';
WITH routes(src,dest) AS (
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
), ids AS (
 SELECT dest,
   to_regclass('public.'||src) AS soid,
   to_regclass('boat_data_stage.'||dest) AS tid,
   to_regclass('boat_data.'||dest) AS vo
 FROM routes
), meta AS (
 SELECT ids.*,
   s.relkind AS skind, t.relkind AS tkind, v.relkind AS vkind,
   (SELECT string_agg(a.attname||':'||a.atttypid||':'||a.atttypmod||':'||
                       a.attnotnull||':'||a.attcollation,';' ORDER BY a.attnum)
    FROM pg_attribute a
    WHERE a.attrelid=ids.soid AND a.attnum>0 AND NOT a.attisdropped) AS src_cols,
   (SELECT string_agg(a.attname||':'||a.atttypid||':'||a.atttypmod||':'||
                       a.attnotnull||':'||a.attcollation,';' ORDER BY a.attnum)
    FROM pg_attribute a
    WHERE a.attrelid=ids.tid AND a.attnum>0 AND NOT a.attisdropped) AS stage_cols,
   (SELECT string_agg(quote_ident(a.attname),',' ORDER BY k.ord)
    FROM pg_index i
    CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum,ord)
    JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
    WHERE i.indrelid=ids.soid AND i.indisprimary AND k.ord<=i.indnkeyatts) AS src_pk,
   (SELECT string_agg(quote_ident(a.attname),',' ORDER BY k.ord)
    FROM pg_index i
    CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum,ord)
    JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
    WHERE i.indrelid=ids.tid AND i.indisprimary AND k.ord<=i.indnkeyatts) AS stage_pk,
   (SELECT count(*) FROM pg_trigger tr
    WHERE tr.tgrelid=ids.soid AND NOT tr.tgisinternal) AS source_user_triggers,
   (SELECT count(*) FROM pg_constraint c WHERE c.conrelid=ids.soid AND c.contype='f') AS source_fk_out,
   (SELECT count(*) FROM pg_constraint c WHERE c.confrelid=ids.soid AND c.contype='f') AS source_fk_in,
   (SELECT count(*) FROM pg_attribute a WHERE a.attrelid=ids.soid
     AND a.attnum>0 AND NOT a.attisdropped AND (a.attidentity<>'' OR a.attgenerated<>'')) AS source_identity_generated,
   (SELECT count(*) FROM pg_attribute a JOIN pg_attrdef d
     ON d.adrelid=a.attrelid AND d.adnum=a.attnum
    WHERE a.attrelid=ids.soid AND a.attnum>0
    AND pg_get_expr(d.adbin,d.adrelid) ~* 'nextval') AS source_serial_defaults
 FROM ids
 LEFT JOIN pg_class s ON s.oid=ids.soid
 LEFT JOIN pg_class t ON t.oid=ids.tid
 LEFT JOIN pg_class v ON v.oid=ids.vo
)
SELECT dest,
  CASE WHEN skind='r' AND tkind='r' AND vkind='v'
       THEN 'PASS' ELSE 'HOLD' END AS relation_shapes,
  CASE WHEN src_cols IS NOT NULL AND stage_cols=src_cols
       THEN 'PASS' ELSE 'HOLD' END AS copy_column_shape,
  coalesce(src_pk,'NONE') AS source_pk,
  coalesce(stage_pk,'NONE') AS stage_pk,
  CASE WHEN src_pk IS NOT NULL AND src_pk=stage_pk
       THEN 'PASS' ELSE 'HOLD_KEY' END AS pk_shape,
  source_user_triggers AS source_triggers,
  source_fk_out AS source_fk_out,
  source_fk_in AS source_fk_in,
  source_identity_generated AS source_identity_generated,
  source_serial_defaults AS source_serial_defaults,
  'NO_CDC_NO_DELTA_APPLY_NO_CUTOVER' AS status
FROM meta ORDER BY dest;
ROLLBACK;
SELECT 'V5_STAGE13_DELTA_CATALOG_READONLY_DONE_NO_TABLE_SCAN_NO_WRITES' AS verdict;
