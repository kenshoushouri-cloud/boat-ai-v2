-- ConoHa V5 physical source gate: official K six-lane results.
-- Absolutely READ ONLY: pg_catalog metadata only, no row scans / writes.
-- Never run ALTER TABLE SET SCHEMA before all writers, views and backup
-- restore have been verified and separately approved.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout = '12000ms';
SET LOCAL lock_timeout = '1500ms';

SELECT 'K_RESULT_SCHEMA_CONTEXT' AS label,
       current_database() AS database,
       current_setting('transaction_read_only') AS read_only;

WITH mapping (source_name, target_name) AS (
 VALUES ('v2_result_entries','raw_racer_results'),
        ('v2_results','raw_results')
), objects AS (
 SELECT m.source_name,m.target_name,s.oid AS source_oid,s.relkind AS source_kind,
        s.relowner,s.reltuples,
        t.oid AS target_oid,t.relkind AS target_kind
 FROM mapping m
 LEFT JOIN pg_namespace ns ON ns.nspname='public'
 LEFT JOIN pg_class s ON s.relnamespace=ns.oid AND s.relname=m.source_name
 LEFT JOIN pg_namespace nt ON nt.nspname='v5_data'
 LEFT JOIN pg_class t ON t.relnamespace=nt.oid AND t.relname=m.target_name
)
SELECT 'K_RESULT_RELATION_GATE' AS label,
       'public.'||source_name AS source,
       'v5_data.'||target_name AS future_physical_name,
       COALESCE(source_kind::text,'MISSING') AS source_relkind,
       COALESCE(target_kind::text,'MISSING') AS target_relkind,
       COALESCE(pg_get_userbyid(relowner),'MISSING') AS source_owner,
       CASE WHEN source_oid IS NOT NULL
            THEN pg_size_pretty(pg_total_relation_size(source_oid))
            ELSE 'n/a' END AS indexed_size,
       CASE WHEN source_oid IS NULL THEN 'BLOCK_SOURCE_MISSING'
            WHEN source_kind NOT IN ('r','p') THEN 'BLOCK_NOT_TABLE'
            WHEN target_oid IS NOT NULL THEN 'BLOCK_TARGET_ALREADY_EXISTS'
            ELSE 'PENDING_WRITER_AND_RESTORE_GATES' END AS preliminary_gate
FROM objects ORDER BY source_name;

WITH tables AS (
 SELECT c.oid,c.relname
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public'
   AND c.relname IN ('v2_result_entries','v2_results')
)
SELECT 'K_RESULT_CONSTRAINT_GATE' AS label,
       t.relname AS source,
       (SELECT COUNT(*) FROM pg_constraint k
         WHERE k.conrelid=t.oid AND k.contype='p') AS primary_key_count,
       (SELECT COUNT(*) FROM pg_constraint k
         WHERE k.conrelid=t.oid AND k.contype='f') AS outgoing_fk_count,
       (SELECT COUNT(*) FROM pg_constraint k
         WHERE k.confrelid=t.oid AND k.contype='f') AS incoming_fk_count,
       (SELECT COUNT(*) FROM pg_trigger tr
         WHERE tr.tgrelid=t.oid AND NOT tr.tgisinternal) AS user_triggers,
       (SELECT COUNT(DISTINCT v.oid) FROM pg_depend d
         JOIN pg_rewrite rw ON rw.oid=d.objid
         JOIN pg_class v ON v.oid=rw.ev_class AND v.relkind IN ('v','m')
         WHERE d.refobjid=t.oid AND d.classid='pg_rewrite'::regclass)
         AS dependent_views
FROM tables t ORDER BY t.relname;

WITH source AS (
 SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname='v2_result_entries'
)
SELECT 'K_RESULT_UNIQUE_INDEX' AS label,
       idx.indexrelid::regclass::text AS index_name,
       idx.indisprimary AS primary,
       idx.indisunique AS unique_index,
       idx.indisvalid AS valid,
       pg_get_indexdef(idx.indexrelid) AS definition
FROM pg_index idx JOIN source s ON idx.indrelid=s.oid
WHERE idx.indisunique
ORDER BY idx.indisprimary DESC, index_name;

-- Match columns needed by save_k_day_results_pg.py's INSERT/UPSERT.
WITH required (column_name) AS (
 VALUES ('race_id'),('lane'),('racer_number'),('racer_name'),
 ('finish_position'),('finish_status'),('motor_no'),('boat_no'),
 ('exhibition_time'),('start_course'),('start_timing'),('start_status'),
 ('is_flying'),('is_late'),('race_time'),('source'),('raw'),
 ('fetched_at'),('updated_at')
), existing AS (
 SELECT a.attname,format_type(a.atttypid,a.atttypmod) AS sql_type
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
 WHERE n.nspname='public' AND c.relname='v2_result_entries'
)
SELECT 'K_RESULT_COLUMN_GATE' AS label,
       COUNT(*) AS required_columns,
       COUNT(e.attname) AS present_columns,
       COUNT(*) - COUNT(e.attname) AS missing_columns,
       COALESCE(string_agg(r.column_name,',' ORDER BY r.column_name)
                FILTER (WHERE e.attname IS NULL),'-') AS missing_names
FROM required r LEFT JOIN existing e ON e.attname=r.column_name;

-- Logical public-facing VIEW is intentionally different from physical target.
SELECT 'K_RESULT_V5_LOGICAL_VIEW_GATE' AS label,
       COALESCE(c.relkind::text,'MISSING') AS v5_racer_results_kind
FROM (SELECT 1) x
LEFT JOIN pg_namespace n ON n.nspname='v5_data'
LEFT JOIN pg_class c ON c.relnamespace=n.oid AND c.relname='racer_results';

COMMIT;
SELECT 'V5_K_RESULT_ENTRIES_CUTOVER_READONLY_COMPLETE_NO_DB_WRITES' AS verdict;
