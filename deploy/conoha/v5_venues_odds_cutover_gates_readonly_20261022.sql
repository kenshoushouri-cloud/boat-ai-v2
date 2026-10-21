-- V5 non-copy physical migration / stage 1B.
-- READ ONLY: metadata gates for the two daily-writer sources missing V5 aliases.
-- No DDL, DML, COPY, filesystem changes, services, network, or sequence updates.
-- Uses PostgreSQL pg_catalog only; never scans 1.4 GB odds row data.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15000ms';
SET LOCAL lock_timeout = '1500ms';

SELECT 'V5_MIGRATION_READONLY_CONTEXT' AS check_name,
       current_database() AS db_name,
       current_setting('transaction_read_only') AS read_only;

WITH targets (src, dest) AS (
  VALUES ('v2_venues','venues'),
         ('v2_odds_trifecta','trifecta_odds')
), rels AS (
 SELECT t.src,t.dest,s.oid AS src_oid,s.relkind,s.reltuples,s.relowner,
        d.oid AS dest_oid,d.relkind AS dest_relkind
 FROM targets t
 LEFT JOIN pg_namespace pn ON pn.nspname='public'
 LEFT JOIN pg_class s ON s.relnamespace=pn.oid AND s.relname=t.src
 LEFT JOIN pg_namespace vn ON vn.nspname='v5_data'
 LEFT JOIN pg_class d ON d.relnamespace=vn.oid AND d.relname=t.dest
)
SELECT 'MIGRATION_RELATION_GATE' AS check_name,
       'public.'||src AS source_name,
       'v5_data.'||dest AS proposed_target,
       CASE relkind WHEN 'r' THEN 'TABLE' WHEN 'p' THEN 'PARTITIONED'
          WHEN 'v' THEN 'VIEW' ELSE COALESCE(relkind::text,'MISSING') END AS source_kind,
       CASE dest_relkind WHEN 'r' THEN 'TABLE' WHEN 'v' THEN 'VIEW'
          WHEN 'p' THEN 'PARTITIONED' ELSE COALESCE(dest_relkind::text,'MISSING') END AS target_kind,
       COALESCE(pg_get_userbyid(relowner),'MISSING') AS source_owner,
       CASE WHEN src_oid IS NOT NULL THEN
         pg_size_pretty(pg_total_relation_size(src_oid)) ELSE 'n/a' END AS size_with_indexes,
       CASE WHEN src_oid IS NOT NULL THEN reltuples::bigint::text
           ELSE 'n/a' END AS estimated_rows_NOT_EXACT,
       CASE WHEN src_oid IS NULL THEN 'BLOCK_NO_SOURCE'
            WHEN relkind NOT IN ('r','p') THEN 'BLOCK_NOT_PLAIN_TABLE'
            WHEN dest_oid IS NOT NULL THEN 'BLOCK_TARGET_NAME_EXISTS'
            ELSE 'PENDING_OTHER_GATES' END AS preliminary_gate
FROM rels ORDER BY source_name;

-- Both collectors call upsert_rows, which uses INSERT ON CONFLICT.
-- Confirm eligible unique keys, not merely that a table exists.
WITH source_tables AS (
 SELECT c.oid, c.relname
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname IN ('v2_venues','v2_odds_trifecta')
)
SELECT 'UNIQUE_INDEX' AS check_name,
       s.relname AS source_name,
       i.indexrelid::regclass::text AS index_name,
       i.indisprimary AS primary_index,
       i.indisunique AS unique_index,
       i.indisvalid AS valid_index,
       i.indisready AS ready_index,
       pg_get_indexdef(i.indexrelid) AS index_definition
FROM source_tables s
JOIN pg_index i ON i.indrelid=s.oid AND i.indisunique
ORDER BY s.relname, i.indisprimary DESC, i.indexrelid::regclass::text;

WITH source_tables AS (
 SELECT c.oid, c.relname
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname IN ('v2_venues','v2_odds_trifecta')
)
SELECT 'FOREIGN_KEY_GATE' AS check_name, s.relname AS source_name,
       (SELECT count(*) FROM pg_constraint fk
         WHERE fk.conrelid=s.oid AND fk.contype='f') AS outgoing_fks,
       (SELECT count(*) FROM pg_constraint fk
         WHERE fk.confrelid=s.oid AND fk.contype='f') AS incoming_fks,
       (SELECT count(*) FROM pg_trigger tr
         WHERE tr.tgrelid=s.oid AND NOT tr.tgisinternal) AS user_triggers,
       (SELECT count(DISTINCT v.oid) FROM pg_depend d
           JOIN pg_rewrite rw ON rw.oid=d.objid
           JOIN pg_class v ON v.oid=rw.ev_class AND v.relkind IN ('v','m')
         WHERE d.refobjid=s.oid AND d.classid='pg_rewrite'::regclass) AS dependent_views
FROM source_tables s ORDER BY source_name;

-- Explicitly show whether the daily writer's conflict columns exist.
WITH source_tables (src, col_a, col_b) AS (
 VALUES ('v2_venues','venue_id',NULL::text),
        ('v2_odds_trifecta','race_id','ticket')
)
SELECT 'UPSERT_COLUMN_GATE' AS check_name,
       x.src AS source_name,x.col_a AS conflict_col_a,
       COALESCE(x.col_b,'-') AS conflict_col_b,
       (a.attnum IS NOT NULL AND NOT a.attisdropped) AS col_a_exists,
       (x.col_b IS NULL OR (b.attnum IS NOT NULL AND NOT b.attisdropped))
            AS col_b_exists
FROM source_tables x
LEFT JOIN pg_namespace n ON n.nspname='public'
LEFT JOIN pg_class c ON c.relnamespace=n.oid AND c.relname=x.src
LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attname=x.col_a AND a.attnum>0
LEFT JOIN pg_attribute b ON b.attrelid=c.oid AND b.attname=x.col_b AND b.attnum>0
ORDER BY x.src;

COMMIT;
SELECT 'V5_VENUES_ODDS_CUTOVER_GATES_READONLY_COMPLETE_NO_DB_WRITES' AS verdict;
