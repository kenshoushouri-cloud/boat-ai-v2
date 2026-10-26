#!/usr/bin/env bash
# Separate realtime collector flock from the long-running native core refresh.
# No schema rescan, no DB writes directly, no changes to old collector.
# --check = read-only; --apply = install realtime-only systemd drop-in and
# trigger one bounded ordinary realtime run. BUY remains OFF.
set -euo pipefail
umask 077
mode="${1:---check}"
[[ "$mode" == "--check" || "$mode" == "--apply" ]] ||
 { echo "HOLD_UNKNOWN_MODE"; exit 2; }
[[ "$(id -u)" -eq 0 ]] || { echo "HOLD_ROOT_REQUIRED"; exit 2; }
svc="boat-v5-native-realtime.service"
timer="boat-v5-native-realtime.timer"
base="/etc/systemd/system/$svc"
dropdir="/etc/systemd/system/$svc.d"
drop="$dropdir/10-independent-realtime-lock.conf"
old="/var/lib/boat-v5-native/collector.lock"
new="/var/lib/boat-v5-native/realtime.lock"
[[ "$(systemctl show "$timer" -p ActiveState --value 2>/dev/null)" == "active" ]] ||
 { echo "HOLD_NATIVE_REALTIME_TIMER_NOT_ACTIVE"; exit 2; }
[[ "$(systemctl show boat-v5-forward-window.timer -p ActiveState --value 2>/dev/null)" == "active" ]] ||
 { echo "HOLD_OLD_FALLBACK_TIMER_NOT_ACTIVE"; exit 2; }
[[ -f "$base" ]] || { echo "HOLD_NATIVE_SERVICE_FILE_MISSING"; exit 2; }
old_exec="ExecStart=/usr/bin/flock -n $old /opt/boat-ai-v5-venv/bin/python -m v5.native_realtime_due_runner --apply --max-races 24"
grep -Fxq -- "$old_exec" "$base" ||
 { echo "HOLD_NATIVE_BASE_EXEC_UNEXPECTED"; exit 2; }
[[ ! -e "$drop" ]] || { echo "HOLD_EXISTING_REALTIME_LOCK_OVERRIDE_REVIEW"; exit 2; }
echo "V5_REALTIME_FLOCK_DIAG_BEGIN"
echo "CORE_REFRESH=$(systemctl show boat-v5-native-core-refresh.service -p ActiveState -p Result --no-pager 2>/dev/null | tr '\n' ' ')"
echo "REALTIME=$(systemctl show "$svc" -p ActiveState -p Result -p ExecMainStatus --no-pager 2>/dev/null | tr '\n' ' ')"
journalctl -u "$svc" --since "2026-10-27 07:00:00" -o cat --no-pager -n 12 2>/dev/null |
 grep -E 'HOLD|ERROR|Traceback|V5_|failed|code|status|RUN' | tail -8 || true
echo "V5_REALTIME_LOCK_SHARED_WITH_CORE_IN_UNIT=YES"
echo "V5_REALTIME_REPLACEMENT_LOCK=$new"
if [[ "$mode" == "--check" ]]; then
 echo "V5_REALTIME_LOCK_FIX_PREFLIGHT_PASS_NO_CHANGES"; exit 0
fi
[[ "${V5_REALTIME_LOCK_FIX_APPROVED:-NO}" == "YES" ]] ||
 { echo "HOLD_EXPLICIT_APPROVAL"; exit 2; }
[[ "$(systemctl is-active "$svc" 2>/dev/null || true)" != "active" ]] ||
 { echo "HOLD_REALTIME_SERVICE_ALREADY_RUNNING"; exit 2; }
install -d -m 0755 "$dropdir"
tmp="$(mktemp "$dropdir/.realtime.XXXXXXXX")"
trap 'rm -f -- "$tmp"' EXIT
cat > "$tmp" <<'UNIT'
[Service]
ExecStart=
ExecStart=/usr/bin/flock -n /var/lib/boat-v5-native/realtime.lock /opt/boat-ai-v5-venv/bin/python -m v5.native_realtime_due_runner --apply --max-races 24
UNIT
chmod 0644 "$tmp"
mv -f -- "$tmp" "$drop"
trap - EXIT
on_error() {
 rm -f -- "$drop"
 systemctl daemon-reload || true
 echo "HOLD_REALTIME_LOCK_OVERRIDE_REVERTED_OLD_COLLECTORS_UNCHANGED"
}
trap on_error ERR
systemctl daemon-reload
effective="$(systemctl show "$svc" -p ExecStart --value)"
[[ "$effective" == *"$new"* ]] ||
 { echo "HOLD_EFFECTIVE_REALTIME_EXEC_MISMATCH"; false; }
[[ "$(systemctl show "$timer" -p ActiveState --value)" == "active" ]] ||
 { echo "HOLD_REALTIME_TIMER_STOPPED"; false; }
trap - ERR
systemctl reset-failed "$svc" || true
if systemctl start --no-block "$svc"; then
 echo "V5_REALTIME_INDEPENDENT_LOCK_INSTALLED_NORMAL_RUN_QUEUED"
else
 echo "HOLD_IMMEDIATE_NATIVE_REALTIME_RUN_NOT_QUEUED_REVIEW_JOURNAL"
fi
echo "V5_NATIVE_TIMER_REMAINS_ACTIVE_OLD_COLLECTORS_UNCHANGED_RESULTS_OFF_BUY_OFF"
echo "CHECK_NATIVE_REALTIME_NEXT_RUN_JOURNAL_AND_REAL_SNAPSHOT_COUNTS"
