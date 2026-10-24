#!/usr/bin/env bash
# Safely shift ONLY V5 results catch-up timer. No collector restart, no BUY,
# no database access, no shadow switch. Fail closed if live schedule differs.
set -Eeuo pipefail
export LC_ALL=C SYSTEMD_PAGER=cat

UNIT=boat-v5-midnight-catchup.timer
DIR=/etc/systemd/system/boat-v5-midnight-catchup.timer.d
OVERRIDE="$DIR/50-early-catchup-20261024.conf"
COMMITTED=0
ADDED=0
TEMP=''

cleanup() {
  local exit_code=$?
  [[ -z "$TEMP" ]] || rm -f "$TEMP"
  if [[ "$ADDED" == 1 && "$COMMITTED" != 1 ]]; then
    echo 'ROLLBACK: restoring original catch-up schedule'
    rm -f "$OVERRIDE"
    systemctl daemon-reload || true
    systemctl restart "$UNIT" || true
  fi
  exit "$exit_code"
}
trap cleanup EXIT

hold() { echo "HOLD: $*" >&2; exit 1; }
[[ "$EUID" -eq 0 ]] || hold 'Run as root in Termius.'
[[ "$(TZ=Asia/Tokyo date +%z)" == '+0900' ]] || hold 'JST clock check failed.'
hour=$(TZ=Asia/Tokyo date +%H)
(( 10#$hour >= 20 && 10#$hour <= 23 )) || hold 'Apply only during 20:00-23:59 JST, before midnight.'
for u in "$UNIT" boat-v5-forward-window.timer boat-v5-daily@night.timer; do
  [[ "$(systemctl show "$u" -p LoadState --value)" == loaded ]] || hold "$u not loaded"
  [[ "$(systemctl show "$u" -p ActiveState --value)" == active ]] || hold "$u not active"
done

[[ -z "$(systemctl show "$UNIT" -p DropInPaths --value)" ]] || hold 'Existing catch-up overrides; manual review required.'
[[ ! -e "$OVERRIDE" ]] || hold 'Target override already exists.'
FRAGMENT=$(systemctl show "$UNIT" -p FragmentPath --value)
[[ -f "$FRAGMENT" && -r "$FRAGMENT" ]] || hold 'Cannot read installed timer.'
EXPECTED=$(printf '%s\n' \
  'OnCalendar=*-*-* 01:20:00 Asia/Tokyo' \
  'OnCalendar=*-*-* 02:20:00 Asia/Tokyo' \
  'OnCalendar=*-*-* 03:20:00 Asia/Tokyo')
ACTUAL=$(grep '^OnCalendar=' "$FRAGMENT" || true)
[[ "$ACTUAL" == "$EXPECTED" ]] || hold 'Installed catch-up times do not match audited baseline.'
FW_FRAGMENT=$(systemctl show boat-v5-forward-window.timer -p FragmentPath --value)
[[ -r "$FW_FRAGMENT" ]] || hold 'Forward timer unavailable.'
grep -Fqx 'OnCalendar=*-*-* 07..23:0/5:00 Asia/Tokyo' "$FW_FRAGMENT" || hold 'Forward timer baseline changed.'
[[ "$(systemctl show "$UNIT" -p ActiveState --value)" == active ]] || hold 'Catch-up timer became inactive.'
command -v systemd-analyze >/dev/null || hold 'systemd-analyze missing.'
for when in '00:45:00' '01:30:00' '02:15:00'; do
  systemd-analyze calendar "*-*-* $when Asia/Tokyo" >/dev/null || hold "Calendar invalid: $when"
done

mkdir -p "$DIR"
TEMP=$(mktemp "$DIR/.v5-catchup.XXXXXX")
cat > "$TEMP" <<'CONF'
[Timer]
# Reset original three OnCalendar entries; only this timer is changed.
OnCalendar=
OnCalendar=*-*-* 00:45:00 Asia/Tokyo
OnCalendar=*-*-* 01:30:00 Asia/Tokyo
OnCalendar=*-*-* 02:15:00 Asia/Tokyo
Persistent=false
CONF
chmod 0644 "$TEMP"
mv -n "$TEMP" "$OVERRIDE"
TEMP=''
[[ -f "$OVERRIDE" ]] || hold 'Could not install override.'
ADDED=1
systemctl daemon-reload
# Restart the timer scheduling only; the .service and running collectors are untouched.
systemctl restart "$UNIT"
[[ "$(systemctl show "$UNIT" -p ActiveState --value)" == active ]] || hold 'Catch-up timer did not reactivate.'
[[ "$(systemctl show "$UNIT" -p DropInPaths --value)" == *"$OVERRIDE"* ]] || hold 'Override not loaded.'
NEXT=$(systemctl show "$UNIT" -p NextElapseUSecRealtime --value)
[[ "$NEXT" == *'00:45:00'* ]] || hold "Unexpected next fire: $NEXT"
COMMITTED=1
echo 'PASS: catch-up schedule applied; old collector untouched; BUY OFF; shadow switch NOT scheduled.'
printf 'Next catch-up: %s\n' "$NEXT"
printf 'Rollback override path: %s\n' "$OVERRIDE"
systemctl cat "$UNIT" --no-pager | grep -E '^(# /|OnCalendar=|Persistent=)' || true
