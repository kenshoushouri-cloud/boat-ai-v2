-- V5 copy-first preflight only. Inspect catalogs/sizes, no table scan, no copy.
-- For ConoHa local database 'railway'. Must NOT execute CREATE/INSERT/ALTER
-- or stop services. Row count from reltuples is ONLY a planner estimate.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10000ms';
SET LOCAL lock_timeout = '1500ms';
WITH pairs(src,dst,group_name) AS (
 VALUES
 ('public.v2_venues','v5_data.venues','core'),
 ('public.v2_races','v5_data.raw_races','core'),
 ('public.v2_race_entries','v5_data.raw_entries','core'),
 ('public.v2_results','v5_data.raw_results','core'),
 ('public.v2_result_entries','v5_data.raw_racer_results','core'),
 ('public.v2_odds_trifecta','v5_data.trifecta_odds','core'),
 ('public.v2_realtime_weather_snapshots','v5_data.raw_weather_snapshots','realtime'),
 ('public.v2_realtime_exhibition_snapshots','v5_data.raw_exhibition_snapshots','realtime'),
 ('public.v2_realtime_entry_snapshots','v5_data.raw_entry_snapshots','realtime'),
 ('public.v2_realtime_odds_snapshots','v5_data.raw_odds_snapshots','realtime'),
 ('public.v2_realtime_race_condition_snapshots','v5_data.raw_race_condition_snapshots','realtime'),
 ('public.v2_realtime_racer_condition_snapshots','v5_data.raw_racer_condition_snapshots','realtime')
), observed AS (
 SELECT p.*,
        to_regclass(p.src) AS src_reg,
        to_regclass(p.dst) AS dst_reg
 FROM pairs p
)
SELECT 'V5_COPY_PREFLIGHT' AS audit,
       group_name,
       src,
       coalesce(sc.relkind::text,'MISSING') AS src_kind,
       CASE WHEN src_reg IS NULL THEN '-' ELSE pg_size_pretty(pg_total_relation_size(src_reg)) END AS src_with_indexes,
       CASE WHEN sc.reltuples < 0 THEN '-' ELSE sc.reltuples::bigint::text END AS est_rows_not_exact,
       dst,
       coalesce(dc.relkind::text,'ABSENT') AS dst_kind,
       (SELECT count(*) FROM pg_constraint c WHERE c.conrelid=o.src_reg AND c.contype='f') AS outgoing_fk,
       (SELECT count(*) FROM pg_constraint c WHERE c.confrelid=o.src_reg AND c.contype='f') AS incoming_fk,
       (SELECT count(*) FROM pg_trigger t WHERE t.tgrelid=o.src_reg AND NOT t.tgisinternal) AS user_triggers
FROM observed o
LEFT JOIN pg_class sc ON sc.oid=o.src_reg
LEFT JOIN pg_class dc ON dc.oid=o.dst_reg
ORDER BY group_name,src;
SELECT 'V5_COPY_CAPACITY' AS audit,
       pg_size_pretty(pg_database_size(current_database())) AS db_size,
       current_database() AS database_name,
       current_setting('server_version',true) AS postgres_version;
COMMIT;
SELECT 'V5_COPY_FIRST_PREFLIGHT_READONLY_DONE_NO_DB_WRITES' AS verdict;
