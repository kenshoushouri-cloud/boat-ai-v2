#!/usr/bin/env bash
# Generic all-venue per-race HOLD isolation. --check never writes/collects.
# --install-only switches native release; does not alter timers/legacy/BUY.
set -euo pipefail
umask 077
mode="${1:---check}"
case "$mode" in --check|--install-only) ;; *) echo HOLD_UNKNOWN_MODE; exit 2;; esac
[[ "$(id -u)" -eq 0 ]] || { echo HOLD_ROOT_REQUIRED; exit 2; }
root="/opt/boat-ai-v5-native"
old="$root/releases/v5exhibition-structured-058b5e3a89debc13c7ce394812037281cdb51d82"
ref="67f7d45f2ebcaed79dd3f39abb307c268d3b0a9c"
new="$root/releases/v5per-race-hold-$ref"
[[ -d "$old" ]] || { echo HOLD_OLD_RELEASE_MISSING; exit 2; }
[[ "$(readlink -f "$root/current")" == "$old" ]] ||
 { echo HOLD_ACTIVE_RELEASE_UNEXPECTED; exit 2; }
[[ ! -e "$new" ]] || { echo HOLD_RELEASE_TARGET_EXISTS; exit 2; }
[[ -x /opt/boat-ai-v5-venv/bin/python ]] || { echo HOLD_VENV_PYTHON_MISSING; exit 2; }
work="$(mktemp -d /tmp/v5-native-per-race.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
chmod 0755 "$work"
cp -a "$old" "$work/release"
mkdir -p "$work/release/tests"
url="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/$ref"
for p in v5/native_realtime_due_runner.py tests/test_v5_native_transition_20261027.py; do
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
    "$url/$p" -o "$work/release/$p"
  chmod 0644 "$work/release/$p"
done
echo "V5_PER_RACE_CONTINUE_OFFLINE_TEST_BEGIN"
(
 cd "$work/release"
 env -u DATABASE_URL -u V5_NATIVE_REALTIME_STAGE_APPROVED \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$work/release" \
  python3 -m unittest discover -s tests \
    -p 'test_v5_native_transition_20261027.py' -v
)
echo "V5_PER_RACE_CONTINUE_OFFLINE_TEST_PASS"
if [[ "$mode" == "--check" ]]; then
 echo V5_PER_RACE_CONTINUE_CHECK_PASS_NO_INSTALL_NO_WRITES
 exit 0
fi
[[ "${V5_PER_RACE_CONTINUE_APPROVED:-NO}" == "YES" ]] ||
 { echo HOLD_EXPLICIT_INSTALL_APPROVAL; exit 2; }
[[ "$(readlink -f "$root/current")" == "$old" ]] ||
 { echo HOLD_ACTIVE_RELEASE_CHANGED_DURING_TEST; exit 2; }
active="$(systemctl is-active boat-v5-native-realtime.service 2>/dev/null || true)"
[[ "$active" != "active" && "$active" != "activating" ]] ||
 { echo HOLD_REALTIME_SERVICE_ACTIVE_TRY_NEXT_IDLE_WINDOW; exit 2; }
[[ "$(systemctl is-active boat-v5-native-realtime.timer 2>/dev/null || true)" == "active" ]] ||
 { echo HOLD_V5_REALTIME_TIMER_NOT_ACTIVE; exit 2; }
[[ "$(systemctl is-active boat-v5-forward-window.timer 2>/dev/null || true)" == "active" ]] ||
 { echo HOLD_LEGACY_FALLBACK_NOT_ACTIVE; exit 2; }
mv "$work/release" "$new"
ln -s "$new" "$root/.next-per-race-$$"
mv -Tf "$root/.next-per-race-$$" "$root/current"
systemctl reset-failed boat-v5-native-realtime.service || true
echo V5_NATIVE_REALTIME_PER_RACE_ISOLATION_INSTALLED
echo V5_REALTIME_TIMER_UNCHANGED_LEGACY_ON_RESULTS_OFF_BUY_OFF
echo NEXT_CONFIRM_JOURNAL_RACE_HOLD_AND_RACE_OK_AND_NATIVE_STAGE_INSERT
