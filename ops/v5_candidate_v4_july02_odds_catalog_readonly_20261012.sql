-- V5 2025-07-02 historical trifecta odds PRE-SCAN metadata gate.
-- Railway > boat-v2-postgres > production > postgres-hobby-fullhistory-candidate-v4 > Data > Query.
-- ONE SELECT on catalogs ONLY, no application rows, no DDL/DML or lock changes.
-- Before any 180-race / 21,600-odds-day read, verify table fields and a valid
-- nonpartial btree index beginning with race_id, as well as SELECT privilege.
-- An is_final flag does not certify that odds were available before a deadline.
WITH required(col,allowed_types) AS (
  VALUES
    ('race_id',ARRAY['text','varchar']::text[]),
    ('ticket',ARRAY['text','varchar']::text[]),
    ('odds',ARRAY['numeric','float4','float8','int2','int4','int8']::text[]),
    ('is_final',ARRAY['bool']::text[]),
    ('fetched_at',ARRAY['timestamptz']::text[])
),
cols AS (
  SELECT r.col, c.udt_name,
         coalesce(c.udt_name = ANY(r.allowed_types),false) AS compatible
  FROM required r
  LEFT JOIN information_schema.columns c
    ON c.table_schema='public'
   AND c.table_name='v2_odds_trifecta'
   AND c.column_name=r.col
),
idx AS (
  SELECT coalesce(bool_or(
           ix.indisvalid AND ix.indisready AND ix.indpred IS NULL
           AND am.amname='btree'
           AND ix.indnkeyatts>=1
           AND a.attname='race_id'
         ),false) AS valid_race_id_first_btree
  FROM pg_class t
  JOIN pg_namespace ns ON ns.oid=t.relnamespace
  JOIN pg_index ix ON ix.indrelid=t.oid
  JOIN pg_class i ON i.oid=ix.indexrelid
  JOIN pg_am am ON am.oid=i.relam
  LEFT JOIN pg_attribute a ON a.attrelid=t.oid
    AND a.attnum=(ix.indkey::int2[])[0]
  WHERE ns.nspname='public' AND t.relname='v2_odds_trifecta'
),
access AS (
  SELECT coalesce(has_table_privilege(
      current_user, to_regclass('public.v2_odds_trifecta'), 'SELECT'
  ),false) AS can_select
),
totals AS (
  SELECT count(*)::int AS checked_fields,
         count(*) FILTER (WHERE compatible)::int AS compatible_fields,
         coalesce(string_agg(
           col || ':' || coalesce(udt_name,'MISSING'),
           ', ' ORDER BY col
         ) FILTER (WHERE NOT compatible),'NONE') AS incompatible_fields
  FROM cols
)
SELECT totals.checked_fields, totals.compatible_fields,
       totals.incompatible_fields,
       idx.valid_race_id_first_btree AS race_id_index_ok,
       access.can_select AS select_privilege_ok,
       CASE WHEN totals.checked_fields=5 AND totals.compatible_fields=5
                 AND idx.valid_race_id_first_btree AND access.can_select
             THEN 'ODDS_CATALOG_OK_NO_DATA_READ_AUTHORIZATION'
            ELSE 'HOLD_ODDS_SCHEMA_OR_INDEX'
       END AS catalog_verdict,
       'NO_ODDS_DATA_SCAN_ROI_FORWARD_OR_BUY_AUTHORIZATION'::text AS authorization
FROM totals CROSS JOIN idx CROSS JOIN access;
