-- V5 official K incident/refund evidence gap - one-day READ ONLY.
-- This diagnoses AFTER-RACE result evidence for research only.
-- Neither clean K rows nor an official result status prove an empty refund section.
-- No feature fitting, original-first-capture claims, Forward / BUY, or writes.
-- Run: psql -v day=2026-10-20 -f /tmp/v5_k_incident_refund_gap.sql
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
\if :{?day}
\else
\set day 2026-10-20
\endif
BEGIN TRANSACTION READ ONLY;
SET LOCAL lock_timeout='1000ms';
SET LOCAL statement_timeout='15000ms';
SET LOCAL work_mem='8MB';

-- One-day official K status census: distinguish confirmed normal K *shape*
-- from independently verified incident/refund evidence (NOT provided here).
WITH target AS MATERIALIZED (
 SELECT race_id FROM boat_data.races
 WHERE race_date=:'day'::date AND race_date>=DATE '2025-07-01'
), k AS MATERIALIZED (
 SELECT r.race_id,
        count(k.lane)::int AS k_rows,
        count(DISTINCT k.lane) FILTER (
          WHERE k.lane BETWEEN 1 AND 6)::int AS valid_lanes,
        count(DISTINCT k.start_course) FILTER (
          WHERE k.start_course BETWEEN 1 AND 6)::int AS valid_courses,
        count(*) FILTER (
          WHERE k.lane BETWEEN 1 AND 6
            AND k.finish_status IN ('01','02','03','04','05','06')
            AND k.finish_position BETWEEN 1 AND 6
            AND k.is_flying IS FALSE AND k.is_late IS FALSE
        )::int AS normal_finish_rows,
        count(*) FILTER (
          WHERE k.lane IS NOT NULL AND
            (k.is_flying IS TRUE OR k.is_late IS TRUE
             OR k.finish_status IN (
               'F','L0','L1','K0','K1','S0','S1','S2',
               '転','落','沈','妨','失格','失','欠','不'
             ))
        )::int AS incident_status_rows,
        count(*) FILTER (
          WHERE k.lane IS NOT NULL
            AND (k.finish_status IS NULL
                 OR k.finish_status NOT IN ('01','02','03','04','05','06',
                   'F','L0','L1','K0','K1','S0','S1','S2',
                   '転','落','沈','妨','失格','失','欠','不')
                 OR k.is_flying IS NULL OR k.is_late IS NULL)
        )::int AS unknown_status_rows,
        count(*) FILTER (
          WHERE k.lane IS NOT NULL
            AND (k.start_course IS NULL
              OR k.start_course NOT BETWEEN 1 AND 6)
        )::int AS missing_course_rows
 FROM target r
 LEFT JOIN public.v2_result_entries k
  ON k.race_id=r.race_id AND k.source='official_k_file'
 GROUP BY r.race_id
), classified AS (
 SELECT race_id,
        CASE
         WHEN k_rows<>6 OR valid_lanes<>6
           THEN 'K_ROW_OR_LANE_INCOMPLETE'
         WHEN incident_status_rows>0
           THEN 'K_INCIDENT_OR_SPECIAL_STATUS'
         WHEN unknown_status_rows>0 OR normal_finish_rows<>6
           THEN 'K_UNKNOWN_OR_NONSTANDARD_FINISH'
         WHEN valid_courses<>6
           THEN 'K_COURSE_INCOMPLETE'
         ELSE 'K_NORMAL_SHAPE_REFUND_NOT_PROVEN'
        END AS k_evidence_class,
        k_rows,incident_status_rows,unknown_status_rows,missing_course_rows
 FROM k
)
SELECT :'day'::date AS inspected_day,
       k_evidence_class,
       count(*)::int AS races,
       sum(incident_status_rows)::int AS incident_status_boat_rows,
       sum(unknown_status_rows)::int AS unknown_boat_rows,
       sum(missing_course_rows)::int AS missing_course_boat_rows,
       'REFUND_SECTION_NOT_INDEPENDENTLY_VERIFIED' AS refund_gate
FROM classified
GROUP BY k_evidence_class
ORDER BY races DESC,k_evidence_class;

-- Metadata inventory only. These names are NOT source authentication.
-- The separately stored boat_history_archive DB is NOT scanned.
SELECT table_schema||'.'||table_name AS relation,
       string_agg(column_name, ',' ORDER BY column_name) AS evidence_name_candidates
FROM information_schema.columns
WHERE table_schema IN ('public','boat_data','v5_data','v5_research')
  AND (
    column_name ~* 'refund|return|void|cancel|incident'
    OR table_name ~* 'refund|return|settle|incident'
  )
GROUP BY 1
ORDER BY relation
LIMIT 25;

COMMIT;
SELECT 'V5_K_INCIDENT_REFUND_GAP_READONLY_NO_CERTIFICATION_NO_BUY' AS audit;
