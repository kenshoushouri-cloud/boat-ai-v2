-- Forensic read-only inspection: why 2026-10-22 Edogawa 3R had
-- zero captured exhibition times. Observations are historical;
-- no backfilled data can be treated as frozen predecision evidence.
-- Show bounded statistics only; never print saved raw page text.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10000ms';
SET LOCAL lock_timeout = '1500ms';

WITH race AS (
 SELECT race_id, deadline_at::timestamptz AS cutoff
 FROM public.v2_races WHERE race_id='20261022_03_03'
), snaps AS (
 SELECT w.snapshot_label, w.snapshot_at, w.source,
        COALESCE(w.raw->>'text','') AS page_text
 FROM public.v2_realtime_weather_snapshots w
 JOIN race r ON r.race_id=w.race_id
 WHERE w.snapshot_at < r.cutoff
)
SELECT 'EDOGAWA3_CAPTURED_PAGE_TEXT' AS audit,
       snapshot_label,
       to_char(snapshot_at AT TIME ZONE 'Asia/Tokyo','YYYY-MM-DD HH24:MI:SS') AS captured_jst,
       source,
       length(page_text) AS saved_text_chars,
       position('展示' IN page_text)>0 AS has_exhibition_word,
       (SELECT count(*) FROM regexp_matches(page_text,
           '(^|[^0-9])[67]\\.[0-9]{2}([^0-9]|$)', 'g')) AS time_shaped_tokens,
       CASE WHEN page_text='' THEN 'NO_TEXT_SAVED'
            ELSE 'TEXT_ONLY_NOT_RAW_HTML' END AS evidence_limit
FROM snaps
ORDER BY snapshot_at DESC
LIMIT 12;

WITH race AS (
 SELECT race_id, deadline_at::timestamptz AS cutoff
 FROM public.v2_races WHERE race_id='20261022_03_03'
)
SELECT 'EDOGAWA3_PREDEADLINE_SNAPSHOT_COUNTS' AS audit,
       (SELECT COUNT(*) FROM public.v2_realtime_weather_snapshots w
         JOIN race r USING (race_id)
         WHERE w.snapshot_at<r.cutoff) AS weather_rows,
       (SELECT COUNT(*) FROM public.v2_realtime_exhibition_snapshots e
         JOIN race r USING (race_id)
         WHERE e.snapshot_at<r.cutoff
           AND e.exhibition_time IS NOT NULL) AS exhibition_time_rows,
       (SELECT COUNT(*) FROM public.v2_realtime_odds_snapshots o
         JOIN race r USING (race_id)
         WHERE o.snapshot_at<r.cutoff AND o.odds>0) AS positive_odds_rows;
COMMIT;
SELECT 'EDOGAWA3_CAPTURE_DIAGNOSTIC_READONLY_COMPLETE' AS verdict;
