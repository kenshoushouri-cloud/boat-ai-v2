#!/usr/bin/env bash
# One paste after 06:00 JST: check stage11 recovery log + October core QA
# plus exact 2026-10-26 six-family realtime source/stage row parity.
# STRICT READ ONLY; NO collector/service change, DELETE, BUY or sync.
set -euo pipefail
export TZ=Asia/Tokyo
if [[ "$(date +%Y%m%d%H%M)" < "202610270600" ]]; then
  echo "HOLD_CHECKPOINT_ONLY_AFTER_20261027_0600_JST"; exit 2
fi
if [[ "$(id -u)" != "0" ]]; then
  echo "HOLD_CHECKPOINT_REQUIRES_ROOT_FOR_PEER_AUTH"; exit 2
fi
core="$(mktemp /tmp/v5-sync-journal.XXXXXXXX.sh)"
realtime="$(mktemp /tmp/v5-oct26-rt-parity.XXXXXXXX.py)"
trap 'rm -f -- "$core" "$realtime"' EXIT
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
  "https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/99fa89a46cdd7657b6c50e9187948c578c526408/deploy/conoha/v5_after_stage11_20261027_readonly_checkpoint.sh" \
  -o "$core"
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
  "https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/f7479904dbcb6de74874217cf9b56241b853d2a3/deploy/conoha/v5_oct26_realtime_exact_parity_readonly_20261027.py" \
  -o "$realtime"
chmod 0644 "$realtime"
echo "V5_POST_SYNC_PARITY_CHECKPOINT_BEGIN_NO_WRITES"
fail=0
echo "=== 03:05 STAGE11 SERVICE JOURNAL + OCT CORE QA ==="
bash "$core" || fail=1
echo "=== OCT26 SIX REALTIME FAMILIES EXACT ROW PARITY ==="
runuser -u postgres -- env DATABASE_URL=postgresql:///railway \
  /opt/boat-ai-v5-venv/bin/python "$realtime" || fail=1
if [[ "$fail" -ne 0 ]]; then
  echo "V5_STAGE_CHECKPOINT_HOLD_PARTIAL_OR_FAILED_KEEP_LEGACY_NO_DELETE"; exit 2
fi
echo "V5_STAGE_CHECKPOINT_FINISHED_INSPECT_ALL_VERDICTS_BEFORE_CUTOVER"
echo "NOT_FULL_HISTORICAL_PARITY_NO_STOP_NO_DELETE_NO_BUY"
