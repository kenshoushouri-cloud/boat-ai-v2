-- V5 2026-05-01 Omura 12R: source lineage for SIX racers only.
-- Read-only ONE SELECT; no internet GET, DDL, DML, DB writes or full-date scan.
-- Execute only on the same confirmed Railway historical PostgreSQL instance.
-- Do not mistake a historical reconstruction for first-seen predecision evidence.
-- Query has not been run against live DB; if missing columns/index, STOP.
WITH race AS MATERIALIZED (
    SELECT race_id, race_date, deadline_at
      FROM public.v2_races
     WHERE race_id = '20260501_24_12'
     LIMIT 1
),
lanes AS MATERIALIZED (
    SELECT r.race_id, r.race_date, r.deadline_at, e.lane,
           e.racer_number, e.racer_class, e.recent_form,
           CASE
               WHEN jsonb_typeof(e.recent_form) = 'array'
                 THEN e.recent_form
               WHEN jsonb_typeof(e.recent_form->'history') = 'array'
                 THEN e.recent_form->'history'
               WHEN jsonb_typeof(e.recent_form->'recent_form') = 'array'
                 THEN e.recent_form->'recent_form'
               ELSE '[]'::jsonb
           END AS parsed_history
      FROM race r
      JOIN public.v2_race_entries e ON e.race_id = r.race_id
     WHERE e.lane BETWEEN 1 AND 6
),
scored AS (
    SELECT l.*,
           jsonb_array_length(l.parsed_history) AS history_total,
           h.history_count,
           h.prior_day_history_count,
           h.unknown_or_late_history_count,
           h.newest_history_date
      FROM lanes l
      LEFT JOIN LATERAL (
          SELECT count(*)::int AS history_count,
                 count(*) FILTER (
                   WHERE item->>'race_date' ~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$'
                     AND (item->>'race_date') < l.race_date::text
                 )::int AS prior_day_history_count,
                 count(*) FILTER (
                   WHERE item->>'race_date' IS NULL
                      OR item->>'race_date' !~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$'
                      OR (item->>'race_date') >= l.race_date::text
                 )::int AS unknown_or_late_history_count,
                 max(item->>'race_date') AS newest_history_date
            FROM (
                SELECT item
                  FROM jsonb_array_elements(l.parsed_history) item
                 LIMIT 5
            ) recent
       ) h ON TRUE
)
SELECT s.race_id, s.lane, s.race_date, s.deadline_at,
       (s.racer_number IS NOT NULL) AS racer_number_present,
       (s.racer_class IS NOT NULL) AS racer_class_present,
       jsonb_typeof(s.recent_form) AS recent_form_json_type,
       s.history_total, s.history_count, s.prior_day_history_count,
       s.unknown_or_late_history_count, s.newest_history_date,
       CASE
          WHEN s.history_total = 0 THEN 'MISSING_HISTORY_OR_UNPARSED'
          WHEN s.history_total > 5 THEN 'HISTORY_EXCEEDS_MODEL_LIMIT_REVIEW'
          WHEN s.history_count = s.prior_day_history_count
             AND s.unknown_or_late_history_count = 0
             THEN 'PRIOR_DAY_DATE_ONLY_NOT_CAPTURE_PROOF'
          ELSE 'HISTORY_DATE_NOT_PRIOR_DAY'
       END AS recent_form_verdict,
       x.snapshot_label, x.source AS exhibition_source,
       x.exhibition_time_rank, x.snapshot_at AS exhibition_snapshot_at,
       x.raw->>'reuse_contract' AS exhibition_reuse_contract,
       x.raw->>'source_contract' AS exhibition_source_contract,
       x.raw->>'source_snapshot_label' AS source_snapshot_label,
       x.raw->>'source_snapshot_at' AS source_snapshot_at_text,
       CASE
          WHEN x.race_id IS NULL THEN 'NO_HISTORICAL_EXHIBITION_ROW'
          WHEN x.exhibition_time_rank IS NULL
            OR x.exhibition_time_rank NOT BETWEEN 1 AND 6
            THEN 'MISSING_OR_INVALID_EXHIBITION_RANK'
          WHEN x.source = 'official_beforeinfo_historical'
            THEN 'HISTORICAL_RETRIEVAL_NOT_PREDECISION_ATTESTED'
          WHEN x.snapshot_at IS NULL OR s.deadline_at IS NULL
            THEN 'EXHIBITION_TIMING_UNKNOWN'
          WHEN x.snapshot_at >= s.deadline_at
            THEN 'SNAPSHOT_AT_OR_AFTER_DEADLINE_NOT_ELIGIBLE'
          WHEN x.raw->>'reuse_contract' =
                   'REALTIME_EXHIBITION_TO_HISTORICAL_V1'
            THEN 'REUSED_BEFORE_DEADLINE_TIMESTAMP_ONLY'
          ELSE 'BEFORE_DEADLINE_TIMESTAMP_ONLY_NOT_AUTHENTICATED'
       END AS exhibition_verdict,
       FALSE AS originally_frozen_predecision_evidence_verified,
       FALSE AS v5_real_roi_verified,
       FALSE AS buy_eligible
  FROM scored s
  LEFT JOIN public.v2_realtime_exhibition_snapshots x
    ON x.race_id = s.race_id
   AND x.lane = s.lane
   AND x.snapshot_label = 'historical'
 ORDER BY s.lane;
