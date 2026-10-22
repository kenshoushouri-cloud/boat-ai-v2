-- Create empty version-neutral data schema on ConoHa's "railway" DB.
-- One narrow guarded DDL action only. No table copy/move, no route changes,
-- no service/timer changes, no deletion. Transactional; rollback on error.
-- Run only after boat_shared_storage_preflight_readonly_20261022.sql PASSES.
\set ON_ERROR_STOP on
\pset pager off
BEGIN;
SET LOCAL lock_timeout = '1500ms';
SET LOCAL statement_timeout = '10000ms';
DO $gate$
DECLARE
  legacy_count bigint;
  staged_count bigint;
  missing_count bigint;
  extra_count bigint;
BEGIN
  IF current_database() <> 'railway' THEN
    RAISE EXCEPTION 'STOP: unexpected database %', current_database();
  END IF;
  IF current_user <> 'postgres' THEN
    RAISE EXCEPTION 'STOP: expected postgres database owner, got %', current_user;
  END IF;
  IF to_regnamespace('boat_data') IS NOT NULL THEN
    RAISE EXCEPTION 'STOP: boat_data schema already exists; inspect, do not rerun';
  END IF;
  IF to_regclass('public.v2_venues') IS NULL
     OR to_regclass('v5_data.venues') IS NULL THEN
    RAISE EXCEPTION 'STOP: source or staged venues table absent';
  END IF;
  IF (SELECT relkind FROM pg_class WHERE oid = to_regclass('public.v2_venues')) <> 'r'
     OR (SELECT relkind FROM pg_class WHERE oid = to_regclass('v5_data.venues')) <> 'r' THEN
    RAISE EXCEPTION 'STOP: source or staged venues not physical tables';
  END IF;

  SELECT count(*) INTO legacy_count FROM public.v2_venues;
  SELECT count(*) INTO staged_count FROM v5_data.venues;
  SELECT count(*) INTO missing_count
    FROM (SELECT * FROM public.v2_venues
          EXCEPT ALL SELECT * FROM v5_data.venues) d;
  SELECT count(*) INTO extra_count
    FROM (SELECT * FROM v5_data.venues
          EXCEPT ALL SELECT * FROM public.v2_venues) d;
  RAISE NOTICE 'VENUES_PARITY source=% staged=% missing=% extra=%',
    legacy_count, staged_count, missing_count, extra_count;
  IF legacy_count <> 24 OR staged_count <> 24
     OR missing_count <> 0 OR extra_count <> 0 THEN
    RAISE EXCEPTION 'STOP: venue parity changed; no DDL allowed';
  END IF;
END;
$gate$;
CREATE SCHEMA boat_data AUTHORIZATION postgres;
SELECT 'BOAT_COMMON_SCHEMA_CREATED' AS audit, nspname AS schema_name,
       pg_get_userbyid(nspowner) AS schema_owner
FROM pg_namespace WHERE nspname = 'boat_data';
COMMIT;
SELECT 'BOAT_COMMON_SCHEMA_ONLY_CREATED_NO_TABLE_MOVE_NO_ROUTE_CHANGE' AS verdict;
