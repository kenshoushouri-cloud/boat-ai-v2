#!/usr/bin/env bash
# Repair ONLY the false-HOLD 2026-10-27 03:05 JST one-shot stage11 timer.
# Original 2026-10-26 scheduler successfully created then stopped it
# because of an incorrect comparison against 2026-10-26 03:05.
# Do not modify legacy collection, DB, VIEW, BUY or live writer.
set -Eeuo pipefail
umask 022
export LC_ALL=C

ORIG="boat-v5-stage11-delta-20261027"
ALT="boat-v5-stage11-delta-20261027-recovery"
TARGET="/usr/local/libexec/boat-v5-stage11-delta-20261027.py"
CLOCK="2026-10-27 03:05:00 Asia/Tokyo"
NEXT_EXPECT="2026-10-27 03:05:00 JST"

hold(){ printf 'HOLD: %s\n' "$*" >&2; exit 2; }
prop(){ systemctl show "$1" -p "$2" --value --no-pager 2>/dev/null || true; }
check_unit(){
  local name="$1" t="$1.timer" svc="$1.service" cat_t cat_s
  [[ "$(prop "$t" LoadState)" == "loaded" ]] || hold "$t is not loaded"
  cat_t=$(systemctl cat "$t" --no-pager) || hold "Cannot inspect $t"
  cat_s=$(systemctl cat "$svc" --no-pager) || hold "Cannot inspect $svc"
  # Verify existing transient timer and service from our pinned scheduler.
  [[ "$cat_t" == *"OnCalendar="*"2026-10-27"*"03:05"* ]] ||
    hold "Unrecognized calendar configuration in $t"
  [[ "$cat_s" == *"$TARGET"* && "$cat_s" == *"--remaining --apply"* &&
     "$cat_s" == *"V5_STAGE12_DELTA_APPROVED=YES"* &&
     "$cat_s" == *"flock"* ]] ||
    hold "Unrecognized stage-only service command in $svc"
}
confirm(){
  local name="$1" t="$1.timer" next state
  state=$(prop "$t" ActiveState)
  next=$(prop "$t" NextElapseUSecRealtime)
  if [[ "$state" != "active" || "$next" != *"$NEXT_EXPECT"* ]]; then
    systemctl stop "$t" >/dev/null 2>&1 || true
    hold "Timer did not validate; stopped $t ActiveState=$state NEXT=$next"
  fi
  echo "PASS: STAGE11_DELTA_ONLY_SCHEDULED_NOT_YET_APPLIED"
  echo "UNIT=$t"
  echo "NEXT=$next"
  echo "STAGE_SCOPE=11_NO_RACES"
  echo "LEGACY_COLLECTION=UNCHANGED LIVE_VIEW=UNCHANGED BUY=OFF CUTOVER=NO_GO"
}

[[ "$(id -u)" == "0" ]] || hold "Run as root in Termius"
[[ "$(TZ=Asia/Tokyo date +%F)" == "2026-10-26" ]] ||
  hold "Only run this recovery on 2026-10-26 JST"
hour=$(TZ=Asia/Tokyo date +%H)
[[ "$hour" =~ ^[0-9][0-9]$ ]] || hold "Unknown JST hour"
((10#$hour >= 8 && 10#$hour <= 23)) || hold "Daytime recovery only"
[[ -f "$TARGET" && -r "$TARGET" && ! -L "$TARGET" ]] ||
  hold "Original vetted stage-only runner unavailable (do not reinstall blindly)"
[[ $(wc -c < "$TARGET") -gt 15000 ]] || hold "Runner unexpectedly short"
grep -Fq 'mx.add_argument("--remaining"' "$TARGET" || hold "Runner lacks --remaining"
grep -Fq 'HOLD_STAGE_DELTA_ONLY_NIGHT_OR_RACES_DAYLIGHT' "$TARGET" ||
  hold "Runner lacks night restriction"
grep -Fq 'V5_STAGE12_DELTA_APPROVED' "$TARGET" || hold "Runner lacks approval check"

for unit in boat-v5-daily@night.timer boat-v5-daily@morning.timer \
            boat-v5-forward-window.timer boat-v5-midnight-catchup.timer; do
  [[ "$(prop "$unit" ActiveState)" == "active" ]] ||
    hold "Legacy collector timer not active or unverified: $unit"
done
for unit in "$ORIG.service" "$ALT.service"; do
  [[ "$(prop "$unit" ActiveState)" != "active" ]] ||
    hold "Stage-only service already running: $unit"
done
command -v systemd-run >/dev/null || hold "Missing systemd-run"
command -v flock >/dev/null || hold "Missing flock"
command -v runuser >/dev/null || hold "Missing runuser"
systemd-analyze calendar "$CLOCK" >/dev/null || hold "Calendar failed to validate"

status=$(prop "$ORIG.timer" LoadState)
case "$status" in
  loaded)
    check_unit "$ORIG"
    state=$(prop "$ORIG.timer" ActiveState)
    case "$state" in
      active) confirm "$ORIG"; exit 0;;
      inactive)
        systemctl start "$ORIG.timer" ||
          hold "Existing transient timer cannot be reactivated"
        confirm "$ORIG"
        exit 0;;
      *) hold "Unexpected existing timer state $state";;
    esac;;
  not-found|"")
    # systemd may garbage-collect a stopped transient timer.
    # Use a fresh unique one-shot name only if the prior timer is gone.
    if [[ "$(prop "$ALT.timer" LoadState)" == "loaded" ]]; then
      check_unit "$ALT"
      [[ "$(prop "$ALT.timer" ActiveState)" == "active" ]] && { confirm "$ALT"; exit 0; }
      [[ "$(prop "$ALT.timer" ActiveState)" == "inactive" ]] ||
        hold "Unknown alternate timer state"
      systemctl start "$ALT.timer" ||
        hold "Cannot restart alternate timer"
    else
      [[ "$(prop "$ALT.timer" LoadState)" == "not-found" ]] ||
        hold "Unrecognized alternate timer LoadState"
      /usr/bin/systemd-run --quiet --unit="$ALT" --on-calendar="$CLOCK" \
        --property=Type=oneshot --property=CPUQuota=50% \
        --property=MemoryMax=750M --property=Nice=10 \
        --property=TimeoutStartSec=9500 \
        /usr/bin/flock -n /run/lock/boat-v5-stage11-delta.lock \
        /usr/sbin/runuser -u postgres -- /usr/bin/env DATABASE_URL=postgresql:///railway \
        V5_STAGE12_DELTA_APPROVED=YES /opt/boat-ai-v5-venv/bin/python \
        "$TARGET" --remaining --apply ||
        hold "Could not create fresh isolated recovery timer"
    fi
    check_unit "$ALT"
    confirm "$ALT";;
  *) hold "Unexpected original timer LoadState: $status";;
esac
