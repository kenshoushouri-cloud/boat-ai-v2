-- V5 seven-day archived research source: one-time PostgreSQL METADATA ONLY.
-- Created from GitHub schema contracts; NOT RUN against Railway/PostgreSQL.
-- Execute on explicitly confirmed history DB only in a READ ONLY transaction,
-- role with SELECT (and no DDL/DML), with statement_timeout <= 2 s.
-- Never infer indexes/column types exist from repository migrations.
-- All SELECTs query catalogs/privileges only; NO application table scan.
-- Stop if required columns/usable index prefixes absent. No schema changes.

-- Q1. Required source columns and ACTUAL PostgreSQL data types.
WITH required(table_name, column_name) AS (
  VALUES
    ('v2_races', 'race_id'),
    ('v2_races', 'race_date'),
    ('v2_races', 'deadline_at'),
    ('v2_race_entries', 'race_id'),
    ('v2_race_entries', 'lane'),
    ('v2_race_entries', 'racer_number'),
    ('v2_race_entries', 'racer_class'),
    ('v2_race_entries', 'recent_form'),
    ('v2_realtime_exhibition_snapshots', 'race_id'),
    ('v2_realtime_exhibition_snapshots', 'lane'),
    ('v2_realtime_exhibition_snapshots', 'snapshot_label'),
    ('v2_realtime_exhibition_snapshots', 'source'),
    ('v2_realtime_exhibition_snapshots', 'snapshot_at'),
    ('v2_realtime_exhibition_snapshots', 'exhibition_time_rank'),
    ('v2_realtime_exhibition_snapshots', 'raw'),
    ('v2_results', 'race_id'),
    ('v2_results', 'result_status'),
    ('v2_results', 'race_status'),
    ('v2_results', 'trifecta_ticket'),
    ('v2_results', 'trifecta_payout_yen')
)
SELECT r.table_name, r.column_name, c.data_type, c.udt_name, c.is_nullable,
       CASE WHEN c.column_name IS NULL THEN 'MISSING' ELSE 'PRESENT_TYPE_REVIEW'
       END AS audit_verdict
  FROM required r
  LEFT JOIN information_schema.columns c
    ON c.table_schema = 'public'
   AND c.table_name = r.table_name
   AND c.column_name = r.column_name
 ORDER BY r.table_name, r.column_name;

-- Q2. VALID, READY, NONPARTIAL B-tree left-prefix indexes for Q1..Q3 joins.
-- Exact key order matters; including columns alone is NOT sufficient.
-- No CREATE INDEX or EXPLAIN ANALYZE here.
WITH required(table_name, index_prefix) AS (
  VALUES
    ('v2_races', ARRAY['race_date']::text[]),
    ('v2_race_entries', ARRAY['race_id', 'lane']::text[]),
    ('v2_realtime_exhibition_snapshots',
       ARRAY['race_id', 'snapshot_label', 'lane']::text[]),
    ('v2_results', ARRAY['race_id']::text[])
),
available AS (
  SELECT tbl.relname::text AS table_name,
         ind.relname::text AS index_name,
         ix.indisvalid, ix.indisready,
         (ix.indpred IS NULL) AS not_partial,
         (am.amname = 'btree') AS is_btree,
         ARRAY(
           SELECT a.attname::text
             FROM unnest(ix.indkey::int2[]) WITH ORDINALITY AS k(attnum, pos)
             LEFT JOIN pg_attribute a
               ON a.attrelid = tbl.oid AND a.attnum = k.attnum
            WHERE k.pos <= ix.indnkeyatts
            ORDER BY k.pos
         ) AS key_columns
    FROM pg_class tbl
    JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
    JOIN pg_index ix ON ix.indrelid = tbl.oid
    JOIN pg_class ind ON ind.oid = ix.indexrelid
    JOIN pg_am am ON am.oid = ind.relam
   WHERE ns.nspname = 'public'
     AND tbl.relname IN (
       'v2_races', 'v2_race_entries',
       'v2_realtime_exhibition_snapshots', 'v2_results'
     )
)
SELECT r.table_name, r.index_prefix,
       COALESCE(BOOL_OR(
         a.indisvalid AND a.indisready AND a.not_partial AND a.is_btree
         AND a.key_columns[1:cardinality(r.index_prefix)] = r.index_prefix
       ), FALSE) AS usable_prefix_index_present,
       STRING_AGG(a.index_name, ', ' ORDER BY a.index_name) AS observed_index_names
  FROM required r
  LEFT JOIN available a ON a.table_name = r.table_name
 GROUP BY r.table_name, r.index_prefix
 ORDER BY r.table_name;

-- Q3. Connection privilege and read-only session status (no credentials).
SELECT current_database() AS database_name,
       current_user AS connected_role,
       current_setting('transaction_read_only') AS transaction_read_only,
       current_setting('statement_timeout') AS statement_timeout,
       has_table_privilege(current_user, 'public.v2_races', 'SELECT')
         AS races_select,
       has_table_privilege(current_user, 'public.v2_race_entries', 'SELECT')
         AS entries_select,
       has_table_privilege(current_user,
          'public.v2_realtime_exhibition_snapshots', 'SELECT')
         AS exhibition_select,
       has_table_privilege(current_user, 'public.v2_results', 'SELECT')
         AS results_select;
