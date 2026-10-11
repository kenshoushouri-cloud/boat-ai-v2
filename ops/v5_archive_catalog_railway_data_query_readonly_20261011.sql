-- V5 metadata check via Railway candidate-v4 historical research DB > Data > Query.
-- SINGLE SELECT. No role/transaction/schema changes, no application table scan.
-- This query is a small metadata inspection, not proof of source identity or
-- authorization to run historical race queries. No application table scans.
WITH required_cols(table_name, column_name, allowed_udt) AS (
  VALUES
    ('v2_races','race_id',ARRAY['text','varchar']::text[]),
    ('v2_races','race_date',ARRAY['date']::text[]),
    ('v2_races','deadline_at',ARRAY['timestamptz']::text[]),
    ('v2_race_entries','race_id',ARRAY['text','varchar']::text[]),
    ('v2_race_entries','lane',ARRAY['int2','int4','int8']::text[]),
    ('v2_race_entries','racer_number',ARRAY['int2','int4','int8']::text[]),
    ('v2_race_entries','racer_class_text',ARRAY['text','varchar']::text[]),
    ('v2_race_entries','recent_form',ARRAY['jsonb']::text[]),
    ('v2_realtime_exhibition_snapshots','race_id',ARRAY['text','varchar']::text[]),
    ('v2_realtime_exhibition_snapshots','lane',ARRAY['int2','int4','int8']::text[]),
    ('v2_realtime_exhibition_snapshots','snapshot_label',ARRAY['text','varchar']::text[]),
    ('v2_realtime_exhibition_snapshots','source',ARRAY['text','varchar']::text[]),
    ('v2_realtime_exhibition_snapshots','snapshot_at',ARRAY['timestamptz']::text[]),
    ('v2_realtime_exhibition_snapshots','exhibition_time_rank',ARRAY['int2','int4','int8']::text[]),
    ('v2_realtime_exhibition_snapshots','raw',ARRAY['jsonb']::text[]),
    ('v2_results','race_id',ARRAY['text','varchar']::text[]),
    ('v2_results','result_status',ARRAY['text','varchar']::text[]),
    ('v2_results','race_status',ARRAY['text','varchar']::text[]),
    ('v2_results','trifecta_ticket',ARRAY['text','varchar']::text[]),
    ('v2_results','trifecta_payout_yen',ARRAY['int4','int8','numeric']::text[])
),
columns_checked AS (
 SELECT r.table_name, r.column_name,
        COALESCE(c.udt_name = ANY(r.allowed_udt),false) AS ok
 FROM required_cols r
 LEFT JOIN information_schema.columns c
   ON c.table_schema='public'
  AND c.table_name=r.table_name AND c.column_name=r.column_name
),
required_indexes(table_name,key_prefix) AS (
 VALUES
   ('v2_races',ARRAY['race_date']::text[]),
   ('v2_race_entries',ARRAY['race_id','lane']::text[]),
   ('v2_realtime_exhibition_snapshots',ARRAY['race_id','snapshot_label','lane']::text[]),
   ('v2_results',ARRAY['race_id']::text[])
),
observed_indexes AS (
 SELECT tbl.relname::text AS table_name,
        ix.indisvalid AND ix.indisready AND ix.indpred IS NULL
           AND am.amname='btree' AS usable,
        ARRAY(
          SELECT a.attname::text
          FROM unnest(ix.indkey::int2[]) WITH ORDINALITY AS k(attnum, pos)
          LEFT JOIN pg_attribute a ON a.attrelid=tbl.oid AND a.attnum=k.attnum
          WHERE k.pos <= ix.indnkeyatts ORDER BY k.pos
        ) AS keys
 FROM pg_class tbl
 JOIN pg_namespace ns ON ns.oid=tbl.relnamespace
 JOIN pg_index ix ON ix.indrelid=tbl.oid
 JOIN pg_class ind ON ind.oid=ix.indexrelid
 JOIN pg_am am ON am.oid=ind.relam
 WHERE ns.nspname='public'
   AND tbl.relname IN ('v2_races','v2_race_entries',
                       'v2_realtime_exhibition_snapshots','v2_results')
),
indexes_checked AS (
 SELECT r.table_name,
        COALESCE(BOOL_OR(o.usable
          AND o.keys[1:cardinality(r.key_prefix)]=r.key_prefix),false) AS ok
 FROM required_indexes r
 LEFT JOIN observed_indexes o ON o.table_name=r.table_name
 GROUP BY r.table_name
),
permissions_checked AS (
 SELECT r.table_name,
        COALESCE(has_table_privilege(current_user,
            to_regclass('public.'||r.table_name),'SELECT'),false) AS ok
 FROM required_indexes r
),
summary AS (
 SELECT (SELECT COUNT(*) FROM columns_checked) AS field_records,
        (SELECT COUNT(*) FROM indexes_checked) AS index_records,
        (SELECT STRING_AGG(table_name||'.'||column_name, ', ' ORDER BY table_name,column_name)
         FROM columns_checked WHERE NOT ok) AS missing_or_wrong_type,
        (SELECT STRING_AGG(table_name, ', ' ORDER BY table_name)
         FROM indexes_checked WHERE NOT ok) AS missing_usable_indexes,
        (SELECT STRING_AGG(table_name, ', ' ORDER BY table_name)
         FROM permissions_checked WHERE NOT ok) AS missing_select_access
)
SELECT CASE WHEN field_records=20 AND index_records=4
                  AND missing_or_wrong_type IS NULL
                  AND missing_usable_indexes IS NULL
                  AND missing_select_access IS NULL
             THEN 'SHAPE_OK_SOURCE_NOT_AUTHENTICATED'
             ELSE 'HOLD_DO_NOT_READ_RACES' END AS check_result,
       field_records AS checked_columns,
       index_records AS checked_indexes,
       COALESCE(missing_or_wrong_type,'NONE') AS problem_columns,
       COALESCE(missing_usable_indexes,'NONE') AS problem_indexes,
       COALESCE(missing_select_access,'NONE') AS problem_select_access,
       'NO_LIVE_DATA_READ_AUTHORIZATION'::text AS permission_to_run_smoke
FROM summary;
