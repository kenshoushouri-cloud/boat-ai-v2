#!/usr/bin/env bash
# Timer/log/row audit and conditional direct official same-day core catchup.
# No schema scans, no legacy changes, no native result timer, no BUY.
set -euo pipefail
umask 077
export TZ=Asia/Tokyo
[[ "$(id -u)" -eq 0 ]] || { echo HOLD_ROOT_REQUIRED; exit 2; }
today="$(date +%Y%m%d)"
since="$(date +%Y-%m-%d) 07:00:00"
echo "V5_COLLECTION_AUDIT_DAY=$today"
on=1
for t in boat-v5-native-core-morning.timer boat-v5-native-core-refresh.timer boat-v5-native-core-night.timer boat-v5-native-realtime.timer; do
  active="$(systemctl is-active "$t" 2>/dev/null || true)"
  enabled="$(systemctl is-enabled "$t" 2>/dev/null || true)"
  echo "NATIVE_TIMER|$t|active=$active|enabled=$enabled"
  if [[ "$active" != active || "$enabled" != enabled ]]; then on=0; fi
done
for t in boat-v5-daily@morning.timer boat-v5-forward-window.timer boat-v5-daily@night.timer boat-v5-midnight-catchup.timer; do
  echo "OLD_TIMER|$t|$(systemctl is-active "$t" 2>/dev/null || true)"
done
echo "V5_RESULTS_TIMER=$(systemctl is-active boat-v5-native-results.timer 2>/dev/null || true)"
raw="$(runuser -u postgres -- psql -XqAt -v ON_ERROR_STOP=1 -d railway -F '|' <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='15000ms';
SELECT
 (SELECT count(*) FROM boat_data_stage.races WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date),
 (SELECT count(*) FROM boat_data_stage.entries e JOIN boat_data_stage.races r ON e.race_id=r.race_id WHERE r.race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date),
 (SELECT count(*) FROM boat_data_stage.entry_snapshots WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date AND source='official_beforeinfo_v5_native'),
 (SELECT count(*) FROM boat_data_stage.exhibition_snapshots WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date AND source='official_beforeinfo_v5_native'),
 (SELECT count(*) FROM boat_data_stage.odds_snapshots WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date AND source='official_odds3t_v5_native'),
 (SELECT count(*) FROM boat_data_stage.weather_snapshots WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date AND source='official_beforeinfo_v5_native'),
 (SELECT count(*) FROM boat_data_stage.race_condition_snapshots WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date AND source='official_beforeinfo_v5_native'),
 (SELECT count(*) FROM boat_data_stage.racer_condition_snapshots WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date AND source='official_beforeinfo_v5_native');
ROLLBACK;
SQL
)"
row="$(printf '%s\n' "$raw" | grep -E '^[0-9]+([|][0-9]+){7}$' || true)"
[[ "$(printf '%s\n' "$row" | grep -Ec '^[0-9]+([|][0-9]+){7}$' || true)" -eq 1 ]] ||
 { echo HOLD_BAD_COUNTS_OUTPUT; exit 2; }
IFS='|' read -r races entries e x o w rc pc <<< "$row"
echo "V5_TODAY_CORE_RACES=$races ENTRIES=$entries"
echo "V5_REALTIME_TODAY_ENTRY=$e EXHIBITION=$x ODDS=$o WEATHER=$w RACE_CONDITION=$rc RACER_CONDITION=$pc"
expected=""
if venues="$(runuser -u postgres -- env PYTHONPATH=/opt/boat-ai-v5-native/current:/opt/boat-ai-v5 /opt/boat-ai-v5-venv/bin/python -c 'from v5.native_official_index_preview import fetch_official_index,official_venues; import sys; day=sys.argv[1]; print(len(official_venues(fetch_official_index(day),day)))' "$today" 2>/dev/null)"; then
  if [[ "$venues" =~ ^[0-9]+$ && "$venues" -gt 0 ]]; then
    expected=$((venues * 12))
    echo "OFFICIAL_VENUES=$venues EXPECTED_RACES=$expected"
  fi
fi
[[ -n "$expected" ]] || echo OFFICIAL_INDEX_NOT_VERIFIED
for service in boat-v5-native-core-refresh.service boat-v5-native-core-morning.service boat-v5-native-realtime.service boat-v5-forward-window.service; do
  echo "SERVICE|$service|$(systemctl show "$service" -p ActiveState -p Result -p ExecMainStatus --no-pager 2>/dev/null | tr '\n' ' ')"
  journalctl -u "$service" --since "$since" -o cat --no-pager -n 18 2>/dev/null |
    grep -E 'V5_|HOLD|ERROR|Traceback|FAILED|failed|success' | tail -7 || true
done
if [[ "$on" -ne 1 ]]; then echo HOLD_NATIVE_TIMER_STATUS_REVIEW; fi
need=0
if [[ -n "$expected" ]]; then
  if (( races < expected || entries < expected * 6 )); then need=1; fi
elif (( races < 12 || entries < races * 6 )); then
  need=1
fi
if [[ "$need" -eq 1 ]]; then
  state="$(systemctl is-active boat-v5-native-core-refresh.service 2>/dev/null || true)"
  if [[ "$state" == active || "$state" == activating ]]; then
    echo V5_TODAY_CORE_INCOMPLETE_REFRESH_IN_PROGRESS_NO_DUPLICATE
  elif systemctl start --no-block boat-v5-native-core-refresh.service; then
    echo V5_TODAY_CORE_REPAIR_REQUESTED_NOW_CHECK_LOGS_AND_ROW_COUNTS_LATER
  else
    echo HOLD_NATIVE_TODAY_CORE_REPAIR_CANNOT_START
    exit 3
  fi
else
  echo V5_TODAY_CORE_ALREADY_COMPLETE_OR_SUFFICIENT_NO_EXTRA_RUN
fi
echo V5_TIMER_AUDIT_END_LEGACY_UNCHANGED_BUY_OFF
