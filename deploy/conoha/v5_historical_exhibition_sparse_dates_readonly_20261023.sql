-- V5 source reconnaissance: EXACTLY 16 chosen sample dates across 2025-07..2026-10.
-- Sparse point-in-time existence check only. NOT a continuous coverage scan,
-- not the true first collection date, not immutable first-write evidence,
-- and not a certification of official source/refunds/predictions/BUY.
-- Same-label six-boat exhibition rank validity matches the prior 10/20 audit.
-- READ ONLY; no writes/DDL/large history joins/HTTP/external archive DB.
-- Run: psql -d railway -X -v ON_ERROR_STOP=1 -f /tmp/v5_ex_sparse.sql
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep ' | '
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='20000ms';
SET LOCAL lock_timeout='1000ms';
SET LOCAL work_mem='8MB';

WITH dates(day) AS MATERIALIZED (
 VALUES
 (DATE '2025-07-15'),
 (DATE '2025-10-15'),
 (DATE '2026-01-15'),
 (DATE '2026-04-15'),
 (DATE '2026-07-15'),
 (DATE '2026-09-15'),
 (DATE '2026-10-01'),
 (DATE '2026-10-05'),
 (DATE '2026-10-10'),
 (DATE '2026-10-15'),
 (DATE '2026-10-17'),
 (DATE '2026-10-18'),
 (DATE '2026-10-19'),
 (DATE '2026-10-20'),
 (DATE '2026-10-21'),
 (DATE '2026-10-22')
), races AS MATERIALIZED (
 SELECT r.race_id,r.race_date,r.deadline_at
 FROM boat_data.races r
 JOIN dates d ON d.day=r.race_date
), ex_labels AS MATERIALIZED (
 SELECT e.race_id,e.snapshot_label,
        count(*)::integer AS n,
        count(DISTINCT e.lane) FILTER (
          WHERE e.lane BETWEEN 1 AND 6
            AND e.exhibition_time_rank BETWEEN 1 AND 6
        )::integer AS n_lanes,
        count(DISTINCT e.exhibition_time_rank) FILTER (
          WHERE e.lane BETWEEN 1 AND 6
            AND e.exhibition_time_rank BETWEEN 1 AND 6
        )::integer AS n_ranks,
        count(*) FILTER (
          WHERE e.snapshot_at < r.deadline_at::timestamptz
            AND e.lane BETWEEN 1 AND 6
            AND e.exhibition_time_rank BETWEEN 1 AND 6
        )::integer AS n_before
 FROM boat_data.exhibition_snapshots e
 JOIN races r ON r.race_id=e.race_id
 GROUP BY e.race_id,e.snapshot_label
), per_race AS MATERIALIZED (
 SELECT race_id,
        bool_or(n=6 AND n_lanes=6 AND n_ranks=6) AS complete6,
        bool_or(n=6 AND n_lanes=6 AND n_ranks=6 AND n_before=6)
          AS labeled_predeadline6,
        bool_or(snapshot_label='historical'
          AND n=6 AND n_lanes=6 AND n_ranks=6) AS historical6,
        bool_or(snapshot_label LIKE 'conoha_forward_%'
          AND n=6 AND n_lanes=6 AND n_ranks=6) AS forward6
 FROM ex_labels GROUP BY race_id
)
SELECT to_char(d.day,'YYYY-MM-DD') AS sampled_day,
       count(r.race_id)::integer AS known_races,
       count(p.race_id)::integer AS races_any_ex_rows,
       count(*) FILTER (WHERE p.complete6)::integer AS complete_same_label6,
       count(*) FILTER (
         WHERE p.labeled_predeadline6
       )::integer AS timestamp_6_NOT_FIRST_WRITE_PROOF,
       count(*) FILTER (WHERE p.historical6)::integer AS historical6,
       count(*) FILTER (WHERE p.forward6)::integer AS forward6
FROM dates d
LEFT JOIN races r ON r.race_date=d.day
LEFT JOIN per_race p ON p.race_id=r.race_id
GROUP BY d.day
ORDER BY d.day;

-- Find alternative exhibit/beforeinfo relations WITHOUT touching their rows.
-- Table existence is not proof that any specific date has usable snapshots.
SELECT table_schema||'.'||table_name AS possible_other_source,
       table_type
FROM information_schema.tables
WHERE table_schema IN ('public','boat_data','v5_data','v5_research')
  AND table_name ~* '(exhibit|beforeinfo)'
ORDER BY 1
LIMIT 35;

COMMIT;
SELECT 'V5_EXHIBITION_16_SPARSE_DATES_READONLY_SAMPLES_NOT_FULL_HISTORY_NO_BUY' AS audit;
