#!/usr/bin/env bash
# One-shot guarded stage-only reconciliation of 11 copied data families.
# Schedules 2026-10-27 03:05 JST ONLY. No production cutover/BUY/source changes.
# Old public writers/13 boat_data VIEWs/timers are never altered here.
set -Eeuo pipefail
umask 022
export LC_ALL=C
NAME="boat-v5-stage11-delta-20261027"
TARGET="/usr/local/libexec/boat-v5-stage11-delta-20261027.py"
COMMIT="f7f52aea5bb30a034a19837d2b449d07eeb3db9b"
URL="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/$COMMIT/deploy/conoha/v5_stage12_delta_reconcile_guarded_20261025.py"

hold(){ echo "HOLD: $*" >&2; exit 2; }
find_bin(){
  local p n="$1"
  p=$(command -v "$n" 2>/dev/null || true)
  [[ "$p" == /* && -x "$p" ]] && { printf '%s' "$p"; return; }
  for p in "/usr/bin/$n" "/usr/sbin/$n" "/bin/$n" "/sbin/$n"; do
    [[ -x "$p" ]] && { printf '%s' "$p"; return; }
  done
  return 1
}
[[ "$(id -u)" == "0" ]] || hold "Run as root in Termius."
[[ "$(TZ=Asia/Tokyo date +%F)" == "2026-10-26" ]] || hold "Use on 2026-10-25 JST only."
HOUR=$(TZ=Asia/Tokyo date +%H)
[[ "$HOUR" =~ ^[0-9][0-9]$ ]] || hold "Unrecognized JST clock."
((10#$HOUR >= 8 && 10#$HOUR <= 23)) || hold "Schedule only 08:00-23:59 JST."
[[ -x /opt/boat-ai-v5-venv/bin/python ]] || hold "Missing V5 Python virtual environment."
[[ -d /opt/boat-ai-v5/.git ]] || hold "V5 checkout absent."
[[ ! -e "$TARGET" ]] || hold "Runner already installed, not overwriting."
FLOCK=$(find_bin flock) || hold "Missing flock"
RUNUSER=$(find_bin runuser) || hold "Missing runuser"
SDRUN=$(find_bin systemd-run) || hold "Missing systemd-run"
SDANALYZE=$(find_bin systemd-analyze) || hold "Missing systemd-analyze"
PSQL=$(find_bin psql) || hold "Missing psql"
[[ "$(systemctl show "$NAME.timer" -p LoadState --value 2>/dev/null || true)" != loaded ]] ||
  hold "The stage11 timer already exists."
[[ "$(systemctl show "$NAME.service" -p ActiveState --value 2>/dev/null || true)" != active ]] ||
  hold "The stage11 service is already running."
for unit in boat-v5-daily@night.timer boat-v5-daily@morning.timer boat-v5-forward-window.timer boat-v5-midnight-catchup.timer; do
  [[ "$(systemctl show "$unit" -p ActiveState --value 2>/dev/null)" == active ]] ||
    hold "Legacy timer state uncertain: $unit"
done
"$SDANALYZE" calendar "2026-10-27 03:05:00 Asia/Tokyo" >/dev/null ||
  hold "Calendar verification failed"
# PG catalog guard, no table scanning: all eleven physical stage targets exist.
count=$("$RUNUSER" -u postgres -- "$PSQL" -X -At -v ON_ERROR_STOP=1 -d railway -c "
SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='boat_data_stage' AND c.relkind='r'
  AND c.relname IN ('entries','results','racer_results','trifecta_odds',
  'racer_course_stats_snapshots','entry_snapshots','exhibition_snapshots',
  'odds_snapshots','weather_snapshots','race_condition_snapshots',
  'racer_condition_snapshots');") || hold "Could not inspect stage catalog"
[[ "$count" == 11 ]] || hold "Expected all eleven physical stage tables, observed $count"
mkdir -p /usr/local/libexec
TMP=$(mktemp /usr/local/libexec/.v5-stage11.XXXXXXXX)
trap 'rm -f "$TMP"' EXIT
curl -fsSL --connect-timeout 10 --max-time 45 --retry 2 "$URL" > "$TMP" ||
  hold "Pinned GitHub runner unavailable."
[[ $(wc -c < "$TMP") -gt 15000 ]] || hold "Downloaded Python unexpectedly short."
grep -Fq 'mx.add_argument("--remaining"' "$TMP" || hold "Expected --remaining not present."
grep -Fq 'V5_STAGE12_DELTA_APPROVED' "$TMP" || hold "Approval guard missing."
grep -Fq 'HOLD_STAGE_DELTA_ONLY_NIGHT_OR_RACES_DAYLIGHT' "$TMP" || hold "Time guard missing."
python3 -m py_compile "$TMP" || hold "Python syntax check failed."
chmod 0644 "$TMP"
# Catalog-only preview: no row scans, no stage writes.
"$RUNUSER" -u postgres -- /usr/bin/env DATABASE_URL=postgresql:///railway \
  /opt/boat-ai-v5-venv/bin/python "$TMP" --remaining || hold "V5 stage11 metadata preview failed."
mv "$TMP" "$TARGET"
trap - EXIT
# One-time transient calendar only. No changes to legacy units.
"$SDRUN" --quiet --unit="$NAME" --on-calendar="2026-10-27 03:05:00 Asia/Tokyo" \
  --property=Type=oneshot --property=CPUQuota=50% \
  --property=MemoryMax=750M --property=Nice=10 \
  --property=TimeoutStartSec=9500 \
  "$FLOCK" -n /run/lock/boat-v5-stage11-delta.lock \
  "$RUNUSER" -u postgres -- /usr/bin/env DATABASE_URL=postgresql:///railway \
  V5_STAGE12_DELTA_APPROVED=YES /opt/boat-ai-v5-venv/bin/python \
  "$TARGET" --remaining --apply || hold "One-shot systemd timer creation failed."
if [[ "$(systemctl show "$NAME.timer" -p ActiveState --value 2>/dev/null)" != active ]]; then
  systemctl stop "$NAME.timer" >/dev/null 2>&1 || true
  hold "Scheduled stage-only job timer not active"
fi
NEXT=$(systemctl show "$NAME.timer" -p NextElapseUSecRealtime --value)
if [[ "$NEXT" != *"2026-10-26 03:05:00"* ]]; then
  systemctl stop "$NAME.timer" >/dev/null 2>&1 || true
  hold "Unexpected next start, timer stopped: $NEXT"
fi
echo "PASS: STAGE11_DELTA_ONLY_SCHEDULED_NOT_YET_APPLIED"
echo "NEXT=$NEXT"
echo "STAGE_SCOPE=11_NO_RACES"
echo "LEGACY_COLLECTION=UNCHANGED LIVE_VIEW=UNCHANGED BUY=OFF CUTOVER=NO_GO"
echo "CHECK: journalctl -u $NAME.service --no-pager -n 100"
