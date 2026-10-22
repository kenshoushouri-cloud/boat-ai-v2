-- ConoHa V5: bounded, read-only, date-scoped REAL input gap classification.
-- Never creates a forecast or permits BUY. Do not modify services.
-- IMPORTANT: v2 realtime snapshot rows are UPSERT/MUTABLE. A snapshot_at
-- earlier than deadline is only a timestamp consistency check, NOT
-- immutable first-capture / decision-time provenance. Even a full
-- 6/6/120 result remains HARD HOLD until frozen as-of evidence and an
-- actual V5 six-racer/trifecta model are independently verified.
-- Run using: psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f <this-file>
-- Date is deliberately fixed; copy/review before auditing another date.
\set ON_ERROR_STOP on
\pset pager off
BEGIN TRANSACTION READ ONLY;
SET LOCAL lock_timeout = '1000ms';
SET LOCAL statement_timeout = '12000ms';
SET LOCAL search_path = pg_catalog, public;

-- Keep this sample bounded: nearest 8 races on October 23 JST, including
-- recently closed races when available. Missing future snapshots can be
-- normal before the 9-24 minute forward collection window.
WITH sampled AS MATERIALIZED (
  SELECT race_id, cutoff
  FROM (
    SELECT race_id, deadline_at::timestamptz AS cutoff
    FROM boat_data.races
    WHERE race_date = DATE '2026-10-23'
      AND deadline_at IS NOT NULL
  ) d
  ORDER BY abs(extract(epoch FROM (cutoff - statement_timestamp()))),
           cutoff, race_id
  LIMIT 8
)
SELECT r.race_id,
       to_char(r.cutoff AT TIME ZONE 'Asia/Tokyo','HH24:MI') AS cutoff_jst,
       CASE
         WHEN r.cutoff > statement_timestamp() + interval '24 minutes'
           THEN 'EARLY'
         WHEN r.cutoff > statement_timestamp() THEN 'BEFORE'
         ELSE 'CLOSED'
       END AS phase,
       coalesce(e.rows_n,0) AS core_rows,
       coalesce(e.lanes_n,0) AS core_lanes,
       coalesce(s.entry_lanes,0) AS entry_pre,
       coalesce(x.exh_lanes,0) AS exhibition_pre,
       coalesce(o.odds_n,0) AS trifecta_pre,
       coalesce(x.late_lanes,0) AS exhibition_after,
       coalesce(o.late_n,0) AS trifecta_after,
       CASE
         WHEN r.cutoff > statement_timestamp() + interval '24 minutes'
              AND (coalesce(s.entry_lanes,0)<6
                   OR coalesce(x.exh_lanes,0)<6
                   OR coalesce(o.odds_n,0)<120)
           THEN 'WAIT_FORWARD_WINDOW'
         WHEN r.cutoff > statement_timestamp()
              AND (coalesce(e.rows_n,0)<>6 OR coalesce(e.lanes_n,0)<>6
                   OR coalesce(s.entry_lanes,0)<6
                   OR coalesce(x.exh_lanes,0)<6
                   OR coalesce(o.odds_n,0)<120)
           THEN 'PENDING_PREDEADLINE_CAPTURE'
         WHEN coalesce(e.rows_n,0)<>6 OR coalesce(e.lanes_n,0)<>6
           THEN 'HOLD_CORE_NOT_SIX'
         WHEN coalesce(s.entry_lanes,0)<6
           THEN 'HOLD_PRE_ENTRY_SNAPSHOT'
         WHEN coalesce(x.exh_lanes,0)<6
           THEN 'HOLD_PRE_EXHIBITION'
         WHEN coalesce(o.odds_n,0)<120
           THEN 'HOLD_PRE_120_ODDS'
         ELSE 'HOLD_FROZEN_ASOF_AND_MODEL_NOT_PROVED'
       END AS verdict
FROM sampled r
LEFT JOIN LATERAL (
  SELECT count(*)::int AS rows_n,
         count(DISTINCT lane) FILTER (WHERE lane BETWEEN 1 AND 6)::int AS lanes_n
  FROM boat_data.entries
  WHERE race_id=r.race_id
) e ON true
LEFT JOIN LATERAL (
  SELECT coalesce(max(n),0)::int AS entry_lanes
  FROM (
    SELECT snapshot_label,
           count(DISTINCT lane) FILTER (
             WHERE lane BETWEEN 1 AND 6 AND racer_number IS NOT NULL
               AND snapshot_at < LEAST(r.cutoff,statement_timestamp())
           ) AS n
    FROM boat_data.entry_snapshots
    WHERE race_id=r.race_id
    GROUP BY snapshot_label
  ) by_label
) s ON true
LEFT JOIN LATERAL (
  SELECT coalesce(max(pre_n),0)::int AS exh_lanes,
         coalesce(max(late_n),0)::int AS late_lanes
  FROM (
    SELECT snapshot_label,
           count(DISTINCT lane) FILTER (
             WHERE lane BETWEEN 1 AND 6 AND exhibition_time IS NOT NULL
               AND snapshot_at < LEAST(r.cutoff,statement_timestamp())
           ) AS pre_n,
           count(DISTINCT lane) FILTER (
             WHERE lane BETWEEN 1 AND 6 AND exhibition_time IS NOT NULL
               AND snapshot_at >= r.cutoff
           ) AS late_n
    FROM boat_data.exhibition_snapshots
    WHERE race_id=r.race_id
    GROUP BY snapshot_label
  ) by_label
) x ON true
LEFT JOIN LATERAL (
  SELECT coalesce(max(pre_n),0)::int AS odds_n,
         coalesce(max(late_n),0)::int AS late_n
  FROM (
    SELECT snapshot_label,
           count(DISTINCT ticket) FILTER (
             WHERE odds>0 AND ticket ~ '^[1-6]-[1-6]-[1-6]$'
               AND split_part(ticket,'-',1)<>split_part(ticket,'-',2)
               AND split_part(ticket,'-',1)<>split_part(ticket,'-',3)
               AND split_part(ticket,'-',2)<>split_part(ticket,'-',3)
               AND snapshot_at < LEAST(r.cutoff,statement_timestamp())
           ) AS pre_n,
           count(DISTINCT ticket) FILTER (
             WHERE odds>0 AND snapshot_at >= r.cutoff
           ) AS late_n
    FROM boat_data.odds_snapshots
    WHERE race_id=r.race_id
    GROUP BY snapshot_label
  ) by_label
) o ON true
ORDER BY r.cutoff, r.race_id;

COMMIT;
SELECT 'V5_ASOF_GAP_READONLY_DONE_NO_FORECAST_NO_BUY' AS audit;
