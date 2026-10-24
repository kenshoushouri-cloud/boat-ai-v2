#!/usr/bin/env bash
# One-time 02:50 JST staging-only copy of the 12 missing shared families.
# Installs only its own transient timer+service; never edits existing timers,
# legacy writers, boat_data views, BUY, backup, or old source tables.
set -Eeuo pipefail
umask 022
export LC_ALL=C
NAME="boat-v5-stage12-copy-20261025"
TARGET="/usr/local/libexec/boat-v5-stage12-snapshot-only-20261024.py"
URL="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/2aeefbe6cd9d50266f8cd9f26b3024daa95af39f/deploy/conoha/v5_stage12_snapshot_only_20261024.py"
fail() { echo "HOLD: $*" >&2; exit 2; }
[[ "$(id -u)" == 0 ]] || fail "Run as root"
[[ "$(TZ=Asia/Tokyo date +%F)" == "2026-10-24" ]] || fail "Scheduling restricted to 2026-10-24 JST"
HOUR=$(TZ=Asia/Tokyo date +%H)
[[ "$HOUR" -ge 20 && "$HOUR" -le 23 ]] || fail "Use only 20:00-23:59 JST"
[[ -x /opt/boat-ai-v5-venv/bin/python ]] || fail "V5 Python virtualenv missing"
[[ -d /opt/boat-ai-v5/.git ]] || fail "V5 checkout missing"
[[ -x /usr/bin/flock && -x /usr/bin/runuser ]] || fail "System utilities unavailable"
[[ ! -e "$TARGET" ]] || fail "Copy runner already installed; do not overwrite"
[[ "$(systemctl show "$NAME.timer" -p LoadState --value 2>/dev/null || true)" != "loaded" ]] || fail "A stage12 timer already exists"
[[ "$(systemctl show "$NAME.service" -p ActiveState --value 2>/dev/null || true)" != "active" ]] || fail "Stage12 service already active"
for u in boat-v5-daily@night.timer boat-v5-midnight-catchup.timer boat-v5-forward-window.timer boat-v5-daily@morning.timer; do
  [[ "$(systemctl show "$u" -p ActiveState --value)" == active ]] || fail "Existing collection timer not active: $u"
done
systemd-analyze calendar "2026-10-25 02:50:00 Asia/Tokyo" >/dev/null || fail "Invalid calendar"
mkdir -p /usr/local/libexec
TEMP=$(mktemp /usr/local/libexec/.boat-v5-stage12.XXXXXXXX)
trap 'rm -f "$TEMP"' EXIT
curl -fsSL --retry 2 --connect-timeout 8 --max-time 35 "$URL" > "$TEMP" || fail "Cannot obtain pinned GitHub copy script"
[[ "$(wc -c < "$TEMP")" -gt 8000 ]] || fail "Unexpected copy script length"
grep -Fq "BOAT_V5_STAGE_ONLY_SNAPSHOT_20261025" "$TEMP" || fail "Copy marker missing"
grep -Fq "boat_data_stage" "$TEMP" || fail "Stage target missing"
python3 -m py_compile "$TEMP" || fail "Python syntax invalid"
chmod 0644 "$TEMP"
mv "$TEMP" "$TARGET"
trap - EXIT
# The service has no network credentials and no database write privileges beyond
# the existing local postgres role. It executes ONLY the pinned staging code.
systemd-run --quiet --unit="$NAME" \
  --on-calendar="2026-10-25 02:50:00 Asia/Tokyo" \
  --property=Type=oneshot \
  --property=TimeoutStartSec=12000 \
  --property=CPUQuota=50% \
  --property=MemoryMax=350M \
  --property=Nice=10 \
  /usr/bin/flock -n /run/lock/boat-v5-stage12-copy.lock \
  /usr/bin/runuser -u postgres -- /usr/bin/env \
  DATABASE_URL=postgresql:///railway V5_STAGE12_COPY_APPROVED=YES \
  /opt/boat-ai-v5-venv/bin/python "$TARGET" || fail "Could not register stage-only one-shot job"
if [[ "$(systemctl show "$NAME.timer" -p ActiveState --value)" != active ]]; then
  systemctl stop "$NAME.timer" >/dev/null 2>&1 || true
  fail "Scheduled timer did not become active"
fi
echo "PASS: V5_STAGE12_COPY_ONLY_SCHEDULED (NOT YET COPIED)"
systemctl show "$NAME.timer" -p NextElapseUSecRealtime -p ActiveState --no-pager
echo "Expected: 2026-10-25 02:50 JST"
echo "Live source: public.v2_* untouched; 13 live boat_data views untouched"
echo "Preserve existing stage venues; only 12 missing physical stage snapshots targeted"
echo "No cutover, no BUY, no legacy collector stop, no Drive writes"
echo "Check after 06:10: journalctl -u $NAME.service --no-pager -n 80"
