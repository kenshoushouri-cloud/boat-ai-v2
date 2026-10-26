#!/usr/bin/env bash
# 06:00+ JST: checkpoint -> full offline tests -> install V5 native source+units.
# WILL NOT enable timers, run official collector, stop old collection or buy.
set -euo pipefail
umask 077
export TZ=Asia/Tokyo
[[ "$(id -u)" == "0" ]] || { echo "HOLD_RUN_AS_ROOT"; exit 2; }
[[ "$(date +%Y%m%d%H%M)" > "202610270600" ]] ||
  { echo "HOLD_ONLY_AFTER_20261027_0600_JST"; exit 2; }
ROOT="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2"
work="$(mktemp -d /tmp/v5-native-morning.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
fetch() {
  local ref="$1" path="$2" output="$3"
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
    "$ROOT/$ref/$path" -o "$output"
}
echo "=== GATE 1: STAGE11 JOURNAL AND 26TH SIX-FAMILY ROW PARITY ==="
fetch 938be58502357cae438eaeeb59902b87b4b8e755 \
 deploy/conoha/v5_post_sync_parity_checkpoint_20261027.sh "$work/after.sh"
bash "$work/after.sh" | tee "$work/after.log"
[[ "$(grep -c "verdict=OCT26_EXACT_ROWS_EQUAL_CURRENT_ONLY" "$work/after.log" || true)" == "6" ]] ||
  { echo "HOLD_NOT_EXACT_SIX_REALTIME_FAMILIES_NO_INSTALL"; exit 2; }
grep -q "V5_AFTER_STAGE11_READ_ONLY_CHECKPOINT_END_NO_DB_WRITES_NO_CANARY_NO_BUY" "$work/after.log" ||
  { echo "HOLD_MISSING_STAGE11_JOURNAL_QA_FINISH"; exit 2; }
if grep -Eq "HOLD_|HOLD_STAGE|HOLD_NO" "$work/after.log"; then
  echo "HOLD_STAGE11_OR_OCT_MONTH_QA_PROBLEM"; exit 2
fi
echo "=== GATE 2: NATIVE END-TO-END OFFLINE UNIT TESTS ==="
fetch 4bfa65d79160f57c85e85f8f5917a72831f01bab \
 deploy/conoha/v5_native_transition_offline_suite_20261027.sh "$work/native-offline.sh"
bash "$work/native-offline.sh" | tee "$work/offline.log"
grep -q "V5_NATIVE_FULL_TRANSITION_OFFLINE_PASS_NO_DB_NO_HTTP_NO_TIMERS_NO_BUY" "$work/offline.log" ||
  { echo "HOLD_NATIVE_OFFLINE_NOT_PASS"; exit 2; }
echo "=== GATE 3: PREPARE V5 INACTIVE UNIT DEFINITIONS ==="
fetch 84ede1aff4fc6ec943b3e515a25e8bae823ce992 \
 deploy/conoha/v5_native_prepare_release_guarded_20261027.sh "$work/install.sh"
bash "$work/install.sh" --check
if [[ "${V5_NATIVE_INSTALL_APPROVED:-NO}" != "YES" ]]; then
  echo "V5_NATIVE_BOOTSTRAP_PREFLIGHT_PASSED_INSTALL_NOT_APPROVED_NO_CHANGES"; exit 0
fi
V5_NATIVE_INSTALL_APPROVED=YES bash "$work/install.sh" --install-only
echo "V5_NATIVE_INSTALLED_BUT_TIMERS_INACTIVE_LEGACY_STILL_RUNNING_BUY_OFF"
echo "NEXT: ONE_RACE_DIRECT_SITE_AND_PHYSICAL_STAGE_CANARY_BEFORE_TIMER_ACTIVATION"
