#!/usr/bin/env bash
# V5 shared stage ONLY. Read-only month-batch race/entry consistency.
# Usage: bash script.sh YYYY-MM [count]   (count=1..3)
# Each month is a separate read-only PostgreSQL transaction, 5s cap.
# Incomplete data copied from old sources is not evidence of original truth.
set -euo pipefail
start="${1:-}"
batch="${2:-1}"
if [[ ! "$start" =~ ^20(25|26)-(0[1-9]|1[0-2])$ ]] || [[ ! "$batch" =~ ^[1-3]$ ]]; then
  echo "Usage: script.sh YYYY-MM [1..3]" >&2; exit 2
fi
if [[ "$start" < "2025-07" || "$start" > "2026-10" ]]; then
  echo "HOLD_OUTSIDE_2025_07_TO_2026_10" >&2; exit 2
fi
if ! command -v psql >/dev/null 2>&1 || ! command -v runuser >/dev/null 2>&1; then
  echo "HOLD_POSTGRES_CLIENT_MISSING" >&2; exit 2
fi
echo "V5_SHARED_STAGE_ONLY_MONTH_BATCH_START start=$start months=$batch"
for ((i=0;i<batch;i++)); do
  first="$(date -d "${start}-01 + $i month" +%Y-%m-%d)"
  last="$(date -d "$first + 1 month" +%Y-%m-%d)"
  ym="${first:0:7}"
  if [[ "$ym" > "2026-10" ]]; then echo "HOLD_MONTH_OUT_OF_SCOPE_$ym" >&2; exit 2; fi
  low="${first//-/}_"
  high="${last//-/}_"
  echo "V5_STAGE_MONTH_CHECK $ym"
  runuser -u postgres -- psql -X -P pager=off -A -F '|' -v ON_ERROR_STOP=1 -d railway <<SQL
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='500ms';
SET LOCAL work_mem='4MB';
WITH r AS MATERIALIZED (
  SELECT race_id
  FROM boat_data_stage.races
  WHERE race_date >= DATE '$first'
    AND race_date < DATE '$last'
), e AS MATERIALIZED (
  SELECT race_id,
         count(*) AS n,
         count(DISTINCT lane) AS lane_count,
         min(lane) AS lane_min,
         max(lane) AS lane_max,
         count(DISTINCT racer_number) AS racer_count,
         count(*) FILTER (
           WHERE lane IS NULL OR lane NOT BETWEEN 1 AND 6
             OR racer_number IS NULL
             OR racer_number NOT BETWEEN 1 AND 9999
         ) AS invalid_number_rows
  FROM boat_data_stage.entries
  WHERE race_id >= '$low'
    AND race_id < '$high'
  GROUP BY race_id
), x AS (
  SELECT r.race_id AS r_id, e.race_id AS e_id,
         e.n, e.lane_count, e.lane_min, e.lane_max, e.racer_count,
         e.invalid_number_rows
  FROM r FULL OUTER JOIN e ON r.race_id=e.race_id
)
SELECT '$ym' AS month,
       count(r_id) AS race_rows,
       count(e_id) AS entry_races,
       coalesce(sum(n),0) AS entry_rows,
       count(*) FILTER (WHERE r_id IS NOT NULL AND e_id IS NULL) AS races_missing_entries,
       count(*) FILTER (WHERE r_id IS NULL AND e_id IS NOT NULL) AS orphan_entry_races,
       count(*) FILTER (WHERE e_id IS NOT NULL AND (
           n<>6 OR lane_count<>6 OR lane_min<>1 OR lane_max<>6
       )) AS invalid_lane_races,
       count(*) FILTER (WHERE e_id IS NOT NULL AND (
           racer_count<>6 OR invalid_number_rows<>0
       )) AS invalid_racer_races,
       CASE
         WHEN count(r_id)=0 OR count(e_id)=0 THEN 'HOLD_NO_STAGE_MONTH'
         WHEN count(*) FILTER (WHERE r_id IS NOT NULL AND e_id IS NULL
                   OR r_id IS NULL AND e_id IS NOT NULL
                   OR (e_id IS NOT NULL AND (n<>6 OR lane_count<>6
                       OR lane_min<>1 OR lane_max<>6 OR racer_count<>6
                       OR invalid_number_rows<>0))) <>0
                   THEN 'HOLD_STAGE_RACE_ENTRY_MISMATCH'
         ELSE 'INTERNAL_OK_STAGE_ONLY_SOURCE_UNVERIFIED'
       END AS verdict
FROM x;
ROLLBACK;
SQL
done
echo "V5_STAGE_MONTH_BATCH_COMPLETE_READ_ONLY_PROVISIONAL_NO_WRITES_NO_BUY"
