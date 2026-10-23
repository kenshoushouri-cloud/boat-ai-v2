-- COMMON CANONICAL boat_data physical-migration readiness, READ ONLY.
-- No COPY, DROP, ALTER, service restart, route changes, data backfills or BUY.
-- The 13 boat_data entries are VIEWs; this audits metadata only.
-- PostgreSQL 'schema' is not an OS directory/shared filesystem folder.
-- Source/VIEW sizes use pg_relation_size estimates of actual on-disk files;
-- reltuples is an ANALYZE ESTIMATE and NOT an exact row count.
-- Snapshot raw payloads are neither selected nor re-created here.
-- Use: sudo -u postgres psql -d railway -X -v ON_ERROR_STOP=1 \
--      -f /tmp/boat_common_inventory.sql
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='12000ms';
SET LOCAL lock_timeout='1000ms';
SET LOCAL work_mem='8MB';

SELECT current_database() AS database_name,
       current_setting('transaction_read_only') AS transaction_read_only,
       CASE WHEN to_regnamespace('boat_data') IS NOT NULL
         THEN 'CANONICAL_SCHEMA_PRESENT' ELSE 'CANONICAL_SCHEMA_ABSENT' END AS schema_status;

WITH mappings(category,legacy,canonical) AS MATERIALIZED (
 VALUES
 ('master','public.v2_venues','boat_data.venues'),
 ('core','public.v2_races','boat_data.races'),
 ('core','public.v2_race_entries','boat_data.entries'),
 ('result','public.v2_results','boat_data.results'),
 ('result','public.v2_result_entries','boat_data.racer_results'),
 ('odds','public.v2_odds_trifecta','boat_data.trifecta_odds'),
 ('feature','public.v2_racer_course_stats_snapshots','boat_data.racer_course_stats_snapshots'),
 ('realtime','public.v2_realtime_entry_snapshots','boat_data.entry_snapshots'),
 ('realtime','public.v2_realtime_exhibition_snapshots','boat_data.exhibition_snapshots'),
 ('realtime','public.v2_realtime_odds_snapshots','boat_data.odds_snapshots'),
 ('realtime','public.v2_realtime_weather_snapshots','boat_data.weather_snapshots'),
 ('realtime','public.v2_realtime_race_condition_snapshots','boat_data.race_condition_snapshots'),
 ('realtime','public.v2_realtime_racer_condition_snapshots','boat_data.racer_condition_snapshots')
), catalog AS (
 SELECT m.*,
        sc.oid AS source_oid,sc.relkind AS source_kind,
        tc.oid AS target_oid,tc.relkind AS target_kind,
        tc.reltuples AS target_estimate_unused
 FROM mappings m
 LEFT JOIN pg_class sc ON sc.oid=to_regclass(m.legacy)
 LEFT JOIN pg_class tc ON tc.oid=to_regclass(m.canonical)
), verdicts AS (
 SELECT c.*,
        CASE WHEN c.source_kind IN ('r','p') AND c.target_kind='v'
              AND pg_relation_is_updatable(c.target_oid,false)=0
              AND EXISTS (
                SELECT 1 FROM pg_rewrite rw
                JOIN pg_depend d
                  ON d.classid='pg_rewrite'::regclass AND d.objid=rw.oid
                 AND d.refclassid='pg_class'::regclass
                WHERE rw.ev_class=c.target_oid AND rw.rulename='_RETURN'
                  AND d.refobjid=c.source_oid
              ) THEN 'SOURCE_PHYSICAL_CANONICAL_READ_VIEW_ONLY'
             ELSE 'STOP_CHECK_RELATION_OR_DEPENDENCY'
        END AS audit_state
 FROM catalog c
)
SELECT category,legacy,canonical,
       coalesce(source_kind::text,'ABSENT') AS source_kind,
       coalesce(target_kind::text,'ABSENT') AS canonical_kind,
       audit_state,
       CASE WHEN source_oid IS NULL THEN '-' ELSE
         pg_size_pretty(pg_total_relation_size(source_oid)) END AS old_physical_bytes_on_disk
FROM verdicts
ORDER BY category,legacy;

-- Catalog only: the one copied venue staging table and other historical /
-- quarantined exhibition-related relations MUST NOT be auto-promoted into
-- prediction data or physically combined without first proving provenance.
WITH candidates(relation,classification) AS (
 VALUES
 ('v5_data.venues','STAGING_NOT_LIVE_CANONICAL'),
 ('public.v2_exhibition','LEGACY_ALTERNATIVE_NOT_PROVEN'),
 ('public.v2_bao_exhibition_shadow_snapshots','RESEARCH_SHADOW'),
 ('public.v2_exhibition_shadow_decisions','RESEARCH_DECISIONS'),
 ('public.v2_exhibition_shadow_results','RESEARCH_RESULTS'),
 ('public.v2_exhibition_st_forward_shadow','RESEARCH_ST_FORWARD'),
 ('public.v4_exhibition_quarantine_20261017','QUARANTINE_DO_NOT_AUTO_PROMOTE')
)
SELECT classification,relation,
       coalesce(c.relkind::text,'ABSENT') AS relation_kind,
       CASE WHEN c.oid IS NULL THEN '-' ELSE
         pg_size_pretty(pg_total_relation_size(c.oid)) END AS on_disk_size,
       CASE WHEN c.oid IS NULL THEN '-'
         ELSE round(c.reltuples::numeric)::text END AS estimated_rows_NOT_EXACT
FROM candidates p
LEFT JOIN pg_class c ON c.oid=to_regclass(p.relation)
ORDER BY classification,relation;

COMMIT;
SELECT 'BOAT_COMMON_PHYSICAL_MIGRATION_CATALOG_READONLY_NO_COPY_NO_WRITER_SWITCH_NO_BUY' AS audit;
