-- V5 data reorganization stage 3: audited 2026-10-21 modern entry fields.
-- ConoHa-local PostgreSQL 'railway'; applies after stage 1 and stage 2.
-- New projection only: no full-table copy, DML on public sources, service changes,
-- policy changes to fixed V5 weights, or promotion of unverified Forward evidence.
-- This view is raw historical/source data, not V5 model-ready feature evidence.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '20s';

DO $$
BEGIN
  IF to_regclass('v5_data.entries') IS NULL
     OR to_regclass('v5_data.races') IS NULL THEN
    RAISE EXCEPTION 'V5 storage stage 1 missing';
  END IF;
  IF to_regclass('v5_data.entry_attributes_raw') IS NOT NULL THEN
    RAISE EXCEPTION 'v5_data.entry_attributes_raw already exists; refusing to overwrite';
  END IF;
END
$$;

-- Explicitly expose only the current primary columns instead of falling back
-- to retired racer_no/class/motor_2rate fields, which are NULL in 2026-10-21 rows.
CREATE VIEW v5_data.entry_attributes_raw AS
SELECT
  e.race_id,
  e.lane,
  e.racer_number,
  e.racer_name,
  e.racer_class,
  e.racer_class_text,
  e.national_win_rate,
  e.national_place2_rate,
  e.national_place3_rate,
  e.local_win_rate,
  e.local_place2_rate,
  e.local_place3_rate,
  e.motor_no,
  e.motor_place2_rate,
  e.motor_place3_rate,
  e.boat_no,
  e.boat_place2_rate,
  e.boat_place3_rate,
  e.recent_form,
  (e.recent_form IS NOT NULL
   AND jsonb_typeof(e.recent_form) = 'array'
   AND e.recent_form <> '[]'::jsonb) AS recent_form_present,
  e.created_at,
  e.updated_at
FROM public.v2_race_entries AS e
OFFSET 0;

COMMENT ON VIEW v5_data.entry_attributes_raw IS
  'Explicit current racer/motor/boat field names from public.v2_race_entries. '
  'NOT authenticated at-deadline input: created_at/updated_at and historical '
  'after-the-fact snapshots do not prove original first observation. '
  'No backfill of missing recent_form; no v24 motor2 shadow values.';

REVOKE ALL ON TABLE v5_data.entry_attributes_raw FROM PUBLIC;
COMMIT;

-- Check schema and one-day completeness without disclosing or copying records.
SELECT table_schema, table_name, is_updatable
FROM information_schema.views
WHERE table_schema='v5_data'
  AND table_name='entry_attributes_raw';

SELECT
  COUNT(*) AS entries,
  COUNT(motor_no) AS motor_number_present,
  COUNT(motor_place2_rate) AS motor_2rate_present,
  COUNT(national_place2_rate) AS racer_2rate_present,
  COUNT(*) FILTER (WHERE recent_form_present) AS recent_form_present
FROM v5_data.entry_attributes_raw
WHERE race_id >= '20261021_' AND race_id < '20261022_';
