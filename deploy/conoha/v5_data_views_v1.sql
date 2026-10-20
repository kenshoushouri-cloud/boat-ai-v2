-- V5 canonical logical storage mapping v1 (ConoHa local PostgreSQL database "railway").
-- One-shot, small metadata-only migration. Existing public tables are never modified,
-- copied, renamed, truncated or deleted. The source retains full data ownership.
-- Prerequisite: v5_data schema is absent; all six public.v2_* source tables exist.
-- Existing real-time collector/service/timers must remain running.
-- OFFSET 0 prevents PostgreSQL auto-updatable views, without changing rows.
-- This is a source-alias layer, NOT a prediction-time leakage filter.
-- Historical after-the-fact snapshots/official results remain ineligible for
-- original-first-observation / Forward / BUY proof unless separately verified.

BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '20s';

CREATE SCHEMA v5_data;
COMMENT ON SCHEMA v5_data IS
  'V5 logical read-only aliases. Source of truth remains existing public.v2_* tables; no duplicate data.';

CREATE VIEW v5_data.races AS
SELECT * FROM public.v2_races OFFSET 0;
COMMENT ON VIEW v5_data.races IS
  'Source public.v2_races. Race date/deadline; source remains writable only through existing collectors.';

CREATE VIEW v5_data.entries AS
SELECT * FROM public.v2_race_entries OFFSET 0;
COMMENT ON VIEW v5_data.entries IS
  'Source public.v2_race_entries. recent_form can be empty; never assert completeness from view existence.';

CREATE VIEW v5_data.results AS
SELECT * FROM public.v2_results OFFSET 0;
COMMENT ON VIEW v5_data.results IS
  'Source public.v2_results. Overall result and trifecta payout; not all six individual finishes.';

CREATE VIEW v5_data.racer_results AS
SELECT * FROM public.v2_result_entries OFFSET 0;
COMMENT ON VIEW v5_data.racer_results IS
  'Source public.v2_result_entries. K-file detailed finishes have known gaps from 2026-10-07.';

CREATE VIEW v5_data.exhibition_snapshots AS
SELECT * FROM public.v2_realtime_exhibition_snapshots OFFSET 0;
COMMENT ON VIEW v5_data.exhibition_snapshots IS
  'Source public.v2_realtime_exhibition_snapshots. Recorded timestamp is not by itself immutable Forward evidence.';

CREATE VIEW v5_data.odds_snapshots AS
SELECT * FROM public.v2_realtime_odds_snapshots OFFSET 0;
COMMENT ON VIEW v5_data.odds_snapshots IS
  'Source public.v2_realtime_odds_snapshots. Validate 120 odds, provenance and actual cutoff separately.';

REVOKE ALL ON SCHEMA v5_data FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA v5_data FROM PUBLIC;

COMMIT;

-- No persistent changes from these verification queries:
SELECT table_schema, table_name, is_updatable
FROM information_schema.views
WHERE table_schema = 'v5_data'
ORDER BY table_name;

SELECT
  pg_size_pretty(pg_database_size(current_database())) AS db_size_after,
  (SELECT count(*) FROM pg_class c
   JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='v5_data' AND c.relkind='v') AS v5_view_count;
