#!/usr/bin/env bash
# Start native V5 core & realtime daily timers alongside old collectors.
# Preflight default. Results timer intentionally held pending real write.
set -euo pipefail
umask 077
export TZ=Asia/Tokyo
mode="${1:---check}"
case "$mode" in --check|--activate|--rollback) ;; *) echo HOLD_BAD_MODE; exit 2;; esac
[[ "$(id -u)" -eq 0 ]] || { echo HOLD_ROOT_REQUIRED; exit 2; }
expected="/opt/boat-ai-v5-native/releases/v5realtime-all-venues-f63bdf36c9d6ae41bba5ec828bd0a61fc7330ee3"
native=(boat-v5-native-core-morning.timer boat-v5-native-core-refresh.timer
        boat-v5-native-core-night.timer boat-v5-native-realtime.timer)
legacy=(boat-v5-daily@morning.timer boat-v5-forward-window.timer)
if [[ "$mode" == "--rollback" ]]; then
 [[ "${V5_PARALLEL_ROLLBACK_APPROVED:-NO}" == "YES" ]] || { echo HOLD_ROLLBACK_APPROVAL; exit 2; }
 for unit in "${native[@]}"; do systemctl disable --now "$unit"; done
 systemctl stop boat-v5-native-core-refresh.service || true
 echo V5_NATIVE_PARALLEL_ROLLED_BACK_OLD_COLLECTORS_UNTOUCHED
 exit 0
fi
[[ "$(readlink -f /opt/boat-ai-v5-native/current)" == "$expected" ]] ||
 { echo HOLD_TESTED_ALL_VENUES_RELEASE_MISSING; exit 2; }
for unit in "${legacy[@]}"; do
 [[ "$(systemctl show "$unit" -p ActiveState --value 2>/dev/null)" == "active" ]] ||
  { echo "HOLD_OLD_FALLBACK_NOT_ACTIVE_$unit"; exit 2; }
done
for unit in "${native[@]}" boat-v5-native-results.timer; do
 [[ "$(systemctl show "$unit" -p LoadState --value 2>/dev/null)" == "loaded" ]] ||
  { echo "HOLD_NATIVE_UNIT_NOT_LOADED_$unit"; exit 2; }
done
[[ "$(systemctl is-active boat-v5-native-results.timer 2>/dev/null || true)" != "active" ]] ||
 { echo HOLD_RESULTS_TIMER_NOT_VERIFIED; exit 2; }
for unit in "${native[@]}"; do
 state="$(systemctl is-active "$unit" 2>/dev/null || true)"
 [[ "$state" != "active" && "$state" != "activating" ]] ||
  { echo "HOLD_NATIVE_ALREADY_ACTIVE_$unit"; exit 2; }
done
for unit in boat-v5-stage11-delta-20261027-recovery.timer boat-v5-stage11-delta-20261027-recovery.service; do
 state="$(systemctl is-active "$unit" 2>/dev/null || true)"
 [[ "$state" != "active" && "$state" != "activating" ]] ||
  { echo HOLD_STAGE_DELTA_ACTIVE; exit 2; }
done
[[ -x /opt/boat-ai-v5-venv/bin/python && -f /opt/boat-ai-v5/repair_month_all_pg.py ]] ||
 { echo HOLD_NATIVE_PYTHON_OR_PARSER_MISSING; exit 2; }
raw="$(runuser -u postgres -- psql -XqAt -d railway -v ON_ERROR_STOP=1 -F "|" <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='6000ms';
SELECT
 (SELECT count(*) FROM boat_data_stage.races WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date),
 (SELECT count(*) FROM boat_data_stage.entries WHERE race_id LIKE to_char(now() AT TIME ZONE 'Asia/Tokyo','YYYYMMDD')||'_%');
ROLLBACK;
SQL
)"
counts="$(printf '%s\n' "$raw" | grep -E '^[0-9]+[|][0-9]+$' || true)"
[[ "$(printf '%s\n' "$counts" | grep -c '|' || true)" -eq 1 ]] ||
 { echo HOLD_UNEXPECTED_STAGE_CORE_COUNTS; exit 2; }
echo "V5_PARALLEL_TODAY_STAGE_CORE_RACES_ENTRIES=$counts"
echo V5_PARALLEL_NATIVE_CORE_SCHEDULE=06:15,11:13,16:13,23:13_JST
echo V5_PARALLEL_REALTIME_5MIN_SCHEDULE=07:02-23:57_JST
if [[ "$mode" == "--check" ]]; then
 echo V5_PARALLEL_AUTO_START_PREFLIGHT_PASS_NO_CHANGES
 exit 0
fi
[[ "${V5_PARALLEL_AUTO_START_APPROVED:-NO}" == "YES" ]] ||
 { echo HOLD_PARALLEL_START_APPROVAL; exit 2; }
[[ ! -e /etc/boat-ai-v5-native/canary.env ]] ||
 { echo HOLD_EXISTING_NATIVE_ENV_NO_BLIND_OVERWRITE; exit 2; }
install -d -m 0750 -o root -g postgres /etc/boat-ai-v5-native
tmp="$(mktemp /etc/boat-ai-v5-native/.native.XXXXXXXX)"
trap 'rm -f -- "$tmp"' EXIT
cat > "$tmp" <<'ENV'
V5_NATIVE_CORE_STAGE_WRITE_APPROVED=YES
V5_NATIVE_REALTIME_STAGE_APPROVED=YES
V5_SHARED_PRIMARY_MODE=CANARY
CONFIRM_V5_SHARED_PRIMARY_CANARY=YES
CONFIRM_LEGACY_WRITES_SEPARATELY=YES
V5_STAGE_DELTA_JOURNAL_VERIFIED=YES
BUY_ENABLED=0
AUTO_BUY=0
ENABLE_PURCHASE=0
ENV
chown root:postgres "$tmp"
chmod 0640 "$tmp"
mv "$tmp" /etc/boat-ai-v5-native/canary.env
trap - EXIT
started=()
undo() { for unit in "${started[@]}"; do systemctl disable --now "$unit" || true; done; }
trap undo ERR
systemctl daemon-reload
for unit in "${native[@]}"; do
 systemctl enable --now "$unit"
 started+=("$unit")
done
for unit in "${native[@]}"; do
 [[ "$(systemctl is-active "$unit")" == "active" ]]
done
trap - ERR
# Run core day-fill now, without blocking the mobile shell; shared flock
# serializes native writers, and old collector keeps covering gaps.
if systemctl start --no-block boat-v5-native-core-refresh.service; then
 echo V5_NATIVE_SAME_DAY_CORE_REFRESH_QUEUED
else
 echo HOLD_NATIVE_SAME_DAY_CORE_REFRESH_START_FAILED_REVIEW_JOURNAL
fi
echo V5_NATIVE_PARALLEL_AUTO_TIMERS_4_ACTIVE_LEGACY_COLLECTORS_UNTOUCHED
echo NATIVE_RESULTS_DISABLED_BUY_OFF_VERIFY_REALTIME_WRITES_BEFORE_OLD_STOP
