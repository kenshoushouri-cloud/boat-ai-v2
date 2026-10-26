#!/usr/bin/env bash
# AFTER native offline tests, 03:05 sync and stage parity review:
# enable V5 native timers while keeping legacy timers unchanged.
# Does NOT stop old collection, replace VIEWs or delete data.
set -euo pipefail
export TZ=Asia/Tokyo
[[ "$(id -u)" == "0" ]] || { echo "HOLD_ROOT_REQUIRED"; exit 2; }
[[ "$(date +%Y%m%d%H%M)" > "202610270600" ]] ||
  { echo "HOLD_0600_CHECKPOINT_NOT_PASSED"; exit 2; }
[[ "${V5_NATIVE_ACTIVATE_APPROVED:-NO}" == "YES" &&
   "${V5_NATIVE_OFFLINE_VERIFIED:-NO}" == "YES" ]] ||
  { echo "HOLD_EXPLICIT_ACTIVATION_AND_OFFLINE_GATES"; exit 2; }
unit="boat-v5-stage11-delta-20261027-recovery.service"
if [[ "$(systemctl show "$unit" -p ActiveState --value)" == "active" ]]; then
  echo "HOLD_STAGE11_STILL_ACTIVE"; exit 2
fi
journal="$(journalctl -u "$unit" --since '2026-10-27 03:00' \
           --until '2026-10-27 06:00' --no-pager -o cat 2>/dev/null || true)"
if ! grep -q 'STAGE12_DELTA_SNAPSHOT_PASS families=11' <<< "$journal" ||
   ! grep -q 'DELTA_TABLE_COMMITTED entries' <<< "$journal" ||
   grep -Eq 'STAGE12_DELTA_HOLD|HOLD_' <<< "$journal"; then
  echo "HOLD_STAGE11_JOURNAL_NOT_FULL_PASS"; exit 2
fi
units=(boat-v5-native-core-morning.timer boat-v5-native-core-night.timer
       boat-v5-native-realtime.timer boat-v5-native-results.timer)
for u in "${units[@]}"; do
  [[ "$(systemctl show "$u" -p LoadState --value)" == "loaded" ]] ||
    { echo "HOLD_NEW_UNIT_MISSING_$u"; exit 2; }
done
[[ -L /opt/boat-ai-v5-native/current ]] ||
  { echo "HOLD_NATIVE_PINNED_RELEASE_NOT_INSTALLED"; exit 2; }
# Do not inherit BUY configuration. Only known stage-only CANARY flags.
install -d -m 0750 -o root -g postgres /etc/boat-ai-v5-native
target="/etc/boat-ai-v5-native/canary.env"
if [[ -e "$target" ]]; then
  echo "HOLD_ENV_EXISTS_NO_BLIND_OVERWRITE"; exit 2
fi
tmp="$(mktemp /etc/boat-ai-v5-native/.canary.XXXXXXXX)"
trap 'rm -f -- "$tmp"' EXIT
cat > "$tmp" <<'ENV'
V5_NATIVE_CORE_STAGE_WRITE_APPROVED=YES
V5_NATIVE_REALTIME_STAGE_APPROVED=YES
V5_NATIVE_RESULTS_STAGE_APPROVED=YES
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
mv "$tmp" "$target"
trap - EXIT
systemctl daemon-reload
for u in "${units[@]}"; do systemctl enable --now "$u"; done
echo "V5_NATIVE_TIMERS_ENABLED_CANARY_ONLY_OLD_COLLECTION_UNCHANGED_BUY_OFF"
echo "NEXT_REQUIRE_NATIVE_REAL_STAGE_ROWS_AND_RESULT_PROOF_BEFORE_OLD_STOP"
