#!/usr/bin/env bash
# Conditional V5 native cutover: old timer disable ONLY when actual native
# 4-schedule service proof, Oct26 exact realtime parity, and 6-family
# new-stage live data are confirmed. Default --check READ ONLY.
# --rollback restores old timers, stops V5 native timers. NO old data deletion.
set -euo pipefail
export TZ=Asia/Tokyo
MODE="${1:---check}"
case "$MODE" in --check|--apply|--rollback) ;; *)
 echo "HOLD_MODE_CHECK_APPLY_ROLLBACK_ONLY"; exit 2;; esac
[[ "$(id -u)" -eq 0 ]] || { echo "HOLD_ROOT_ONLY"; exit 2; }
OLD=(boat-v5-forward-window.timer boat-v5-daily@morning.timer
     boat-v5-daily@night.timer boat-v5-midnight-catchup.timer)
NEW=(boat-v5-native-core-morning.timer boat-v5-native-core-night.timer
     boat-v5-native-realtime.timer boat-v5-native-results.timer)
if [[ "$MODE" == "--rollback" ]]; then
  [[ "${V5_LEGACY_ROLLBACK_APPROVED:-NO}" == "YES" ]] ||
    { echo "HOLD_ROLLBACK_APPROVAL_REQUIRED"; exit 2; }
  for unit in "${NEW[@]}"; do systemctl disable --now "$unit"; done
  for unit in "${OLD[@]}"; do systemctl enable --now "$unit"; done
  echo "V5_ROLLBACK_OLD_TIMERS_RESTORED_NATIVE_TIMERS_STOPPED_BUY_OFF"
  exit 0
fi
if [[ "$MODE" == "--apply" && "${V5_LEGACY_STOP_APPROVED:-NO}" != "YES" ]]; then
  echo "HOLD_STOP_APPROVAL_REQUIRED"; exit 2
fi
echo "V5_NATIVE_SWITCH_GATE_BEGIN mode=$MODE"
for unit in "${NEW[@]}"; do
  if [[ "$(systemctl show "$unit" -p ActiveState --value 2>/dev/null)" != "active" ]]; then
    echo "HOLD_NATIVE_TIMER_NOT_ACTIVE_$unit"; exit 2
  fi
done
for svc in boat-v5-native-core-morning.service boat-v5-native-core-night.service \
           boat-v5-native-realtime.service boat-v5-native-results.service; do
  status="$(systemctl show "$svc" -p Result --value 2>/dev/null || true)"
  code="$(systemctl show "$svc" -p ExecMainStatus --value 2>/dev/null || true)"
  finished="$(systemctl show "$svc" -p ExecMainExitTimestamp --value 2>/dev/null || true)"
  if [[ "$status" != "success" || "$code" != "0" ||
        ! "$finished" =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
    echo "HOLD_NATIVE_SERVICE_UNVERIFIED_$svc"; exit 2
  fi
  day="${BASH_REMATCH[1]}"
  lower="$(date -d "2 days ago" +%F)"
  if [[ "$day" < "$lower" ]]; then
    echo "HOLD_NATIVE_SERVICE_STALE_$svc"; exit 2
  fi
done
# Hard proof: physical V5 writes, not only successful unit execution.
counts="$(runuser -u postgres -- psql -XAt -v ON_ERROR_STOP=1 \
  -d railway -F '|' <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='5000ms';
SELECT
 (SELECT count(*) FROM boat_data_stage.races
   WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date),
 (SELECT count(*) FROM boat_data_stage.entries
   WHERE race_id LIKE to_char(now() AT TIME ZONE 'Asia/Tokyo','YYYYMMDD')||'_%'),
 (SELECT count(*) FROM boat_data_stage.entry_snapshots
   WHERE source='official_beforeinfo_v5_native'
     AND race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date),
 (SELECT count(*) FROM boat_data_stage.exhibition_snapshots
   WHERE source='official_beforeinfo_v5_native'
     AND race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date),
 (SELECT count(*) FROM boat_data_stage.odds_snapshots
   WHERE source='official_odds3t_v5_native'
     AND race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date),
 (SELECT count(*) FROM boat_data_stage.weather_snapshots
   WHERE source='official_beforeinfo_v5_native'
     AND race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date),
 (SELECT count(*) FROM boat_data_stage.race_condition_snapshots
   WHERE source='official_beforeinfo_v5_native'
     AND race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date),
 (SELECT count(*) FROM boat_data_stage.racer_condition_snapshots
   WHERE source='official_beforeinfo_v5_native'
     AND race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date),
 (SELECT count(*) FROM boat_data_stage.results
   WHERE source='official_v5_native_result'
     AND race_date >= ((now() AT TIME ZONE 'Asia/Tokyo')::date - INTERVAL '2 days');
ROLLBACK;
SQL
)" || { echo "HOLD_DB_PROOF_QUERY_FAILED"; exit 2; }
line="$(printf "%s\n" "$counts" | grep -E '^[0-9]+(\|[0-9]+){8}$' | tail -n 1)"
IFS='|' read -r races entries en ex odd weather rc racer results <<< "$line"
for n in "$races" "$entries" "$en" "$ex" "$odd" "$weather" "$rc" "$racer" "$results"; do
  if [[ ! "$n" =~ ^[0-9]+$ || "$n" -eq 0 ]]; then
    echo "HOLD_NATIVE_STAGE_WRITE_PROOF_INCOMPLETE"; exit 2
  fi
done
# Oct26 exact key+contents parity for ALL SIX historic realtime families.
audit="$(mktemp /tmp/v5-cutover-parity.XXXXXXXX.py)"
trap 'rm -f -- "$audit"' EXIT
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
  "https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/f7479904dbcb6de74874217cf9b56241b853d2a3/deploy/conoha/v5_oct26_realtime_exact_parity_readonly_20261027.py" \
  -o "$audit"
chmod 0644 "$audit"
output="$(runuser -u postgres -- env DATABASE_URL=postgresql:///railway \
   /opt/boat-ai-v5-venv/bin/python "$audit")" ||
  { echo "HOLD_OCT26_PARITY_EXECUTION_FAILED"; exit 2; }
good="$(grep -Ec 'verdict=OCT26_EXACT_ROWS_EQUAL_CURRENT_ONLY' <<< "$output" || true)"
[[ "$good" -eq 6 ]] || { echo "HOLD_OCT26_NOT_EXACT_ALL_SIX"; exit 2; }
for unit in "${OLD[@]}"; do
  active="${unit%.timer}.service"
  if [[ "$(systemctl show "$active" -p ActiveState --value 2>/dev/null)" == "active" ]]; then
    echo "HOLD_LEGACY_COLLECTOR_CURRENTLY_RUNNING_$active"; exit 2
  fi
done
if [[ "$MODE" == "--check" ]]; then
 echo "V5_NATIVE_SWITCH_GATE_READY_MANUAL_APPROVAL_AND_STOP_ONLY_NO_CHANGES"
 exit 0
fi
# Stop old scheduler units only; preserve physical old tables for rollback.
stopped=()
restore_stopped() {
  for unit in "${stopped[@]}"; do systemctl enable --now "$unit" || true; done
}
trap restore_stopped ERR
for unit in "${OLD[@]}"; do
  systemctl disable --now "$unit"
  stopped+=("$unit")
done
trap - ERR
echo "V5_NATIVE_PRIMARY_ACTIVE_LEGACY_TIMERS_DISABLED_ROLLBACK_AVAILABLE"
echo "OLD_TABLES_PRESERVED_BUY_OFF_NO_DELETE"
