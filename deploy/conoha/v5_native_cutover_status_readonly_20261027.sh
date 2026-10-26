#!/usr/bin/env bash
# V5 native cutover evidence summary, READ ONLY; never stops/deletes old system.
set -euo pipefail
export TZ=Asia/Tokyo
echo "V5_NATIVE_CUTOVER_STATUS_READ_ONLY_BEGIN"
echo "=== COLLECTOR AND TIMER NAMES (NO ENV, NO EXECSTART) ==="
systemctl list-timers --all --no-pager --no-legend 2>/dev/null |
  grep -Ei 'boat-v5|boat-v21|boat-v4|native' |
  sed -E 's/[[:space:]]+/ /g' | head -n 25 || true
echo "=== CANONICAL STAGE/LEGACY VIEW AND REAL WRITER EVIDENCE ==="
runuser -u postgres -- psql -X -A -F '|' -P pager=off -v ON_ERROR_STOP=1 -d railway <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='500ms';
SELECT 'relation' AS type,
       x.name,
       COALESCE(c.relkind::text,'ABSENT') AS relkind
FROM (VALUES
 ('boat_data.races'),('boat_data.entries'),
 ('boat_data.odds_snapshots'),('boat_data.exhibition_snapshots'),
 ('boat_data_stage.races'),('boat_data_stage.entries'),
 ('boat_data_stage.odds_snapshots'),
 ('public.v2_races'),('public.v2_race_entries')
) x(name)
LEFT JOIN pg_class c ON c.oid=to_regclass(x.name);
SELECT 'stage_races_today' AS metric, count(*)::text AS total
FROM boat_data_stage.races
WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date;
SELECT 'stage_entries_today' AS metric, count(*)::text AS total
FROM boat_data_stage.entries
WHERE race_id >= to_char(now() AT TIME ZONE 'Asia/Tokyo','YYYYMMDD')||'_'
 AND race_id < to_char((now() AT TIME ZONE 'Asia/Tokyo')::date + interval '1 day','YYYYMMDD')||'_';
SELECT 'native_stage_realtime_today_'||q.family AS metric,
       q.n::text AS total
FROM (
  SELECT 'entry' AS family, count(*) AS n
  FROM boat_data_stage.entry_snapshots
  WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date
    AND source='official_beforeinfo_v5_native'
  UNION ALL
  SELECT 'exhibition',count(*) FROM boat_data_stage.exhibition_snapshots
  WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date
    AND source='official_beforeinfo_v5_native'
  UNION ALL
  SELECT 'odds',count(*) FROM boat_data_stage.odds_snapshots
  WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date
    AND source='official_odds3t_v5_native'
  UNION ALL
  SELECT 'weather',count(*) FROM boat_data_stage.weather_snapshots
  WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date
    AND source='official_beforeinfo_v5_native'
  UNION ALL
  SELECT 'race_condition',count(*) FROM boat_data_stage.race_condition_snapshots
  WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date
    AND source='official_beforeinfo_v5_native'
  UNION ALL
  SELECT 'racer_condition',count(*) FROM boat_data_stage.racer_condition_snapshots
  WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date
    AND source='official_beforeinfo_v5_native'
) q ORDER BY q.family;
ROLLBACK;
SQL
echo "V5_NATIVE_CUTOVER_STATUS_COMPLETE_NO_WRITES_NO_STOP_NO_DELETE_NO_BUY"
echo "NOT_AN_AUTOMATIC_STOP_OR_DELETE_AUTHORIZATION"
