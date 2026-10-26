#!/usr/bin/env bash
# Prepare V5 morning, noon/afternoon, night, 5-minute realtime & 3 result retries.
# Default CHECK ONLY. --install-disabled updates only native timer templates
# with backups; does NOT enable/start native timers or touch legacy.
set -euo pipefail
umask 077
export TZ=Asia/Tokyo
mode="${1:---check}"
[[ "$mode" == "--check" || "$mode" == "--install-disabled" ]] ||
  { echo "HOLD_MODE_CHECK_OR_INSTALL_DISABLED_ONLY"; exit 2; }
[[ "$(id -u)" == "0" ]] || { echo "HOLD_ROOT_REQUIRED"; exit 2; }
root="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2"
ref="563a3b9b9080c8f257ff472455d1109f03a33628"
base="deploy/conoha/native_units"
units=(
  boat-v5-native-core-morning.timer
  boat-v5-native-core-refresh.service
  boat-v5-native-core-refresh.timer
  boat-v5-native-core-night.timer
  boat-v5-native-realtime.timer
  boat-v5-native-results.timer
)
native_timers=(
  boat-v5-native-core-morning.timer
  boat-v5-native-core-refresh.timer
  boat-v5-native-core-night.timer
  boat-v5-native-realtime.timer
  boat-v5-native-results.timer
)
native_services=(
  boat-v5-native-core-morning.service
  boat-v5-native-core-refresh.service
  boat-v5-native-core-night.service
  boat-v5-native-realtime.service
  boat-v5-native-results.service
)
echo "V5_NATIVE_SCHEDULE_PREPARE_MODE=$mode NO_BUY_NO_LEGACY_STOP"
for unit in "${native_timers[@]}" "${native_services[@]}"; do
  state="$(systemctl show "$unit" -p ActiveState --value 2>/dev/null || true)"
  if [[ "$state" == "active" || "$state" == "activating" ]]; then
    echo "HOLD_NATIVE_ALREADY_RUNNING_$unit"; exit 2
  fi
done
for unit in "${native_timers[@]}"; do
  if [[ "$unit" != "boat-v5-native-core-refresh.timer" ]]; then
    [[ -f "/etc/systemd/system/$unit" ]] ||
      { echo "HOLD_NATIVE_UNIT_NOT_INSTALLED_$unit"; exit 2; }
  fi
  enable_state="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
  if [[ "$enable_state" == "enabled" ]]; then
    echo "HOLD_NATIVE_TIMER_ENABLED_$unit"; exit 2
  fi
done
for unit in "${native_services[@]}"; do
  if [[ "$unit" != "boat-v5-native-core-refresh.service" ]]; then
    [[ -f "/etc/systemd/system/$unit" ]] ||
      { echo "HOLD_NATIVE_SERVICE_NOT_INSTALLED_$unit"; exit 2; }
  fi
done
[[ ! -e /etc/systemd/system/boat-v5-native-core-refresh.timer &&
   ! -e /etc/systemd/system/boat-v5-native-core-refresh.service ]] ||
   { echo "HOLD_REFRESH_UNIT_ALREADY_PRESENT_REVIEW_REQUIRED"; exit 2; }
work="$(mktemp -d /tmp/v5-native-schedule.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
for unit in "${units[@]}"; do
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
    "$root/$ref/$base/$unit" -o "$work/$unit"
done
echo "=== VALIDATE JAPAN TIME CALENDAR EXPRESSIONS ==="
for unit in "${native_timers[@]}"; do
  grep -q '^Unit=boat-v5-native-' "$work/$unit" ||
    { echo "HOLD_NATIVE_TIMER_SERVICE_TARGET_$unit"; exit 2; }
  while IFS= read -r expression; do
    systemd-analyze calendar "$expression" >/dev/null ||
      { echo "HOLD_INVALID_CALENDAR_$unit"; exit 2; }
    printf 'TIMER|%s|%s\n' "$unit" "$expression"
  done < <(sed -n 's/^OnCalendar=//p' "$work/$unit")
done
grep -q '^ExecStart=/usr/bin/flock' "$work/boat-v5-native-core-refresh.service" ||
 { echo "HOLD_REFRESH_WRITER_NOT_GATED"; exit 2; }
if [[ "$mode" == "--check" ]]; then
  echo "V5_NATIVE_ALL_DAY_SCHEDULE_VALID_NO_INSTALL_NO_ACTIVATION"; exit 0
fi
[[ "${V5_NATIVE_SCHEDULE_PREP_APPROVED:-NO}" == "YES" ]] ||
 { echo "HOLD_EXPLICIT_SCHEDULE_INSTALL_APPROVAL"; exit 2; }
backup="/etc/boat-ai-v5-native/schedule-backups/v5-20261027-$(date +%s)"
install -d -m 0700 "$backup"
for unit in "${units[@]}"; do
  if [[ -e "/etc/systemd/system/$unit" ]]; then
    cp -p "/etc/systemd/system/$unit" "$backup/$unit"
  fi
done
restore() {
  for unit in "${units[@]}"; do
    if [[ -f "$backup/$unit" ]]; then
      cp -p "$backup/$unit" "/etc/systemd/system/$unit"
    else
      rm -f "/etc/systemd/system/$unit"
    fi
  done
  systemctl daemon-reload || true
  echo "V5_NATIVE_SCHEDULE_ROLLED_BACK_UNITS_OLD_COLLECTION_UNCHANGED"
}
trap restore ERR
for unit in "${units[@]}"; do
  install -m 0644 "$work/$unit" "/etc/systemd/system/.$unit.new"
  mv -f "/etc/systemd/system/.$unit.new" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
for unit in "${native_timers[@]}"; do
  [[ "$(systemctl is-active "$unit" 2>/dev/null || true)" != "active" ]] ||
    { echo "HOLD_NEW_NATIVE_TIMER_BECAME_ACTIVE_$unit"; false; }
  [[ "$(systemctl is-enabled "$unit" 2>/dev/null || true)" != "enabled" ]] ||
    { echo "HOLD_NEW_NATIVE_TIMER_ENABLED_$unit"; false; }
done
trap - ERR
echo "V5_NATIVE_ALL_DAY_SCHEDULE_INSTALLED_TIMERS_DISABLED"
echo "V5_NATIVE_SCHEDULE_BACKUP=$backup"
echo "CORE=06:15,11:13,16:13,23:13_JST REALTIME=07:02-23:57_EVERY5MIN RESULTS=00:55,01:55,02:55_JST"
echo "OLD_COLLECTORS_UNCHANGED_NATIVE_TIMERS_NOT_STARTED_BUY_OFF"
