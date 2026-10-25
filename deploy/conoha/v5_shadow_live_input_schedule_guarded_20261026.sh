#!/usr/bin/env bash
# V5 PAPER/SHADOW input watcher: only reads existing 13 VIEWs.
# No official HTTP, no duplicate collector, DB write, route change or BUY.
# One bounded immediate check + transient 5-minute timer (no reboot persistence).
set -Eeuo pipefail
export LC_ALL=C
umask 022
NAME="boat-v5-shadow-live-readonly"
TARGET="/usr/local/libexec/v5-shadow-live-input-readonly-20261026.py"
COMMIT="4756ce1d3043ba48efdc17c889431f4bd86ac720"
URL="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/$COMMIT/deploy/conoha/v5_shadow_live_input_readonly_20261026.py"
hold(){ printf 'HOLD: %s\n' "$*" >&2; exit 2; }

[[ "$(id -u)" -eq 0 ]] || hold "Root Termius session required"
[[ "$(TZ=Asia/Tokyo date +%F)" == "2026-10-26" ]] || hold "Use this one-day pilot on 2026-10-26 JST only"
[[ -x /opt/boat-ai-v5-venv/bin/python ]] || hold "V5 Python venv absent"
[[ "$(systemctl is-active boat-v5-forward-window.timer)" == active ]] ||
  hold "Existing V5 realtime capture timer NOT active; do not start a second collector"
[[ "$(systemctl is-active boat-v5-daily@morning.timer)" == active ]] ||
  hold "Existing morning input timer NOT active; do not change schedule blindly"
[[ "$(systemctl show "$NAME.timer" -p LoadState --value 2>/dev/null || true)" != loaded ]] ||
  hold "V5 shadow input timer already installed; do NOT duplicate"
[[ ! -e "$TARGET" ]] || hold "Shadow watcher already present; do NOT overwrite"
command -v systemd-run >/dev/null || hold "systemd-run unavailable"
command -v systemd-analyze >/dev/null || hold "systemd-analyze unavailable"
command -v flock >/dev/null || hold "flock unavailable"
command -v runuser >/dev/null || hold "runuser unavailable"
mkdir -p /usr/local/libexec
TEMP=$(mktemp /usr/local/libexec/.v5-shadow-XXXXXXXX)
trap 'rm -f "$TEMP"' EXIT
curl -fsSL --connect-timeout 8 --max-time 30 --retry 1 "$URL" > "$TEMP" ||
 hold "Cannot download pinned GitHub watcher"
[[ "$(wc -c < "$TEMP")" -gt 4500 ]] || hold "Downloaded watcher too short"
grep -Fq 'REPEATABLE READ READ ONLY' "$TEMP" || hold "Read-only guard absent"
grep -Fq 'V5_SHADOW_READONLY_PASS' "$TEMP" || hold "Success marker absent"
/opt/boat-ai-v5-venv/bin/python -m py_compile "$TEMP" || hold "Watcher syntax check failed"
chmod 0644 "$TEMP"
mv "$TEMP" "$TARGET"
trap - EXIT
echo "=== V5 live VIEW input read-only first sample ==="
if ! runuser -u postgres -- /usr/bin/env DATABASE_URL=postgresql:///railway \
 V5_SHADOW_READONLY=YES /opt/boat-ai-v5-venv/bin/python "$TARGET"; then
  rm -f "$TARGET"
  hold "No timer installed because read-only first sample failed"
fi
CAL='*-*-* 07..23:0/5:00 Asia/Tokyo'
systemd-analyze calendar "$CAL" >/dev/null ||
 hold "Invalid 5-minute shadow timer calendar"
systemd-run --quiet --unit="$NAME" --on-calendar="$CAL" \
  --property=Type=oneshot --property=TimeoutStartSec=30 \
  --property=CPUQuota=15% --property=MemoryMax=256M \
  --property=Nice=10 \
  /usr/bin/flock -n /run/lock/boat-v5-shadow-readonly.lock \
  /usr/sbin/runuser -u postgres -- /usr/bin/env \
  DATABASE_URL=postgresql:///railway V5_SHADOW_READONLY=YES \
  /opt/boat-ai-v5-venv/bin/python "$TARGET" ||
    hold "Read-only timer installation failed"
[[ "$(systemctl show "$NAME.timer" -p ActiveState --value)" == active ]] ||
  hold "Timer not active after installation"
echo "PASS: V5_SHADOW_INPUT_READONLY_STARTED_WITH_LIVE_VIEWS"
systemctl show "$NAME.timer" -p ActiveState -p NextElapseUSecRealtime --no-pager
echo "NO_ADDITIONAL_HTTP=YES EXISTING_COLLECTORS=UNTOUCHED BUY=OFF"
echo "NOT_REAL_MODEL_SCORING_YET=YES STAGE_WRITER_CUTOVER=NO_GO"
echo "CHECK: journalctl -u $NAME.service --since '2026-10-26 07:00' --no-pager -n 30"
