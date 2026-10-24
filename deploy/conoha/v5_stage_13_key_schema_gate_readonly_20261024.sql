-- V5 13-source stage copy schema gate; catalogs only, no user-table scans.
-- Outputs source shape and key/default/identity hazards for all 13 types.
-- Read-only transaction; no COPY, no CREATE/DROP/ALTER, no view switch.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '

BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '12000ms';
SET LOCAL lock_timeout = '1200ms';
SET LOCAL work_mem = '8MB';

WITH source(relname) AS (
 VALUES
 ('public.v2_venues'),
 ('public.v2_races'),
 ('public.v2_race_entries'),
 ('public.v2_results'),
 ('public.v2_result_entries'),
 ('public.v2_odds_trifecta'),
 ('public.v2_racer_course_stats_snapshots'),
 ('public.v2_realtime_entry_snapshots'),
 ('public.v2_realtime_exhibition_snapshots'),
 ('public.v2_realtime_odds_snapshots'),
 ('public.v2_realtime_weather_snapshots'),
 ('public.v2_realtime_race_condition_snapshots'),
 ('public.v2_realtime_racer_condition_snapshots')
), target AS (
 SELECT relname, to_regclass(relname) AS src FROM source
), attr AS (
 SELECT t.relname,
        count(a.attnum)::int AS columns,
        count(*) FILTER (WHERE a.attnotnull)::int AS not_null_columns,
        count(*) FILTER (WHERE a.attidentity <> '')::int AS identity_columns,
        count(*) FILTER (WHERE a.attgenerated <> '')::int AS generated_columns,
        count(*) FILTER (WHERE d.adbin IS NOT NULL)::int AS columns_with_defaults,
        count(*) FILTER (WHERE d.adbin IS NOT NULL AND
          pg_get_expr(d.adbin,d.adrelid) ~* 'nextval|sequence')::int AS sequence_default_columns,
        count(*) FILTER (WHERE a.atttypid IN ('json'::regtype,'jsonb'::regtype))::int AS json_columns
 FROM target t JOIN pg_attribute a ON a.attrelid=t.src AND
   a.attnum>0 AND NOT a.attisdropped
 LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
 GROUP BY t.relname
), idx AS (
 SELECT t.relname,
        count(*) FILTER (WHERE i.indisprimary)::int AS pk_indexes,
        count(*) FILTER (WHERE i.indisunique)::int AS unique_indexes,
        count(*) FILTER (WHERE i.indisunique AND
          (i.indpred IS NOT NULL OR i.indexprs IS NOT NULL))::int AS partial_or_expression_unique,
        string_agg(pg_get_indexdef(i.indexrelid), ' ;; ' ORDER BY i.indexrelid)
          FILTER (WHERE i.indisprimary) AS pk_definition
 FROM target t JOIN pg_index i ON i.indrelid=t.src
 GROUP BY t.relname
)
SELECT t.relname AS source,
       CASE WHEN c.oid IS NULL THEN 'MISSING' ELSE c.relkind::text END AS kind,
       coalesce(a.columns,0) AS cols,
       coalesce(a.not_null_columns,0) AS not_null,
       coalesce(a.columns_with_defaults,0) AS defaults,
       coalesce(a.sequence_default_columns,0) AS shared_sequence_risk,
       coalesce(a.identity_columns,0) AS identity,
       coalesce(a.generated_columns,0) AS generated,
       coalesce(a.json_columns,0) AS json_fields,
       coalesce(i.pk_indexes,0) AS pk,
       coalesce(i.unique_indexes,0) AS unique_indexes,
       coalesce(i.partial_or_expression_unique,0) AS special_unique,
       coalesce((SELECT count(*) FROM pg_constraint f
        WHERE f.conrelid=t.src AND f.contype='f'),0) AS fk_out,
       coalesce((SELECT count(*) FROM pg_constraint f
        WHERE f.confrelid=t.src AND f.contype='f'),0) AS fk_in,
       coalesce((SELECT count(*) FROM pg_trigger tr
        WHERE tr.tgrelid=t.src AND NOT tr.tgisinternal),0) AS user_triggers,
       coalesce(i.pk_definition,'NONE') AS pk_def
FROM target t
LEFT JOIN pg_class c ON c.oid=t.src
LEFT JOIN attr a ON a.relname=t.relname
LEFT JOIN idx i ON i.relname=t.relname
ORDER BY t.relname;

ROLLBACK;
SELECT 'V5_STAGE_13_KEY_SCHEMA_READ_ONLY_NO_COPY' AS verdict;
