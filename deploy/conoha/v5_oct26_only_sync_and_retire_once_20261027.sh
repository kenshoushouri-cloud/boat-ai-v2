#!/usr/bin/env bash
# 2026-10-26-only 12-family source->stage insert-missing sync,
# verify 00:45 catchup, ALL date parity, then retire ONLY 03:05 one-shot.
# Does NOT stop existing collectors, remove source, change VIEWs or BUY.
set -euo pipefail
umask 077
export TZ=Asia/Tokyo
if [[ "$(id -u)" != 0 ]]; then echo "HOLD_ROOT_REQUIRED"; exit 2; fi
now="$(date +%Y%m%d%H%M)"
if [[ "$now" < "202610270050" || "$now" > "202610270229" ]]; then
  echo "HOLD_ONLY_20261027_0050_TO_0229_JST"; exit 2
fi
catchup="boat-v5-midnight-catchup.service"
timer="boat-v5-stage11-delta-20261027-recovery.timer"
service="boat-v5-stage11-delta-20261027-recovery.service"
echo "=== VERIFY CATCHUP COMPLETED (NO SERVICE CHANGES) ==="
result="$(systemctl show "$catchup" -p Result --value 2>/dev/null || true)"
active="$(systemctl show "$catchup" -p ActiveState --value 2>/dev/null || true)"
exit_time="$(systemctl show "$catchup" -p ExecMainExitTimestamp --value 2>/dev/null || true)"
echo "CATCHUP_RESULT=$result ACTIVE=$active LAST_EXIT=$exit_time"
if [[ "$result" != "success" || "$active" == "active" || "$exit_time" != *"2026-10-27"* ]]; then
  echo "HOLD_0045_CATCHUP_NOT_CERTIFIED_NO_SYNC"; exit 2
fi
state="$(systemctl show "$service" -p ActiveState --value 2>/dev/null || true)"
if [[ "$state" == "active" || "$state" == "activating" ]]; then
  echo "HOLD_STAGE11_ALREADY_RUNNING"; exit 2
fi
next="$(systemctl show "$timer" -p NextElapseUSecRealtime --value 2>/dev/null || true)"
current="$(systemctl show "$timer" -p ActiveState --value 2>/dev/null || true)"
echo "STAGE11_TIMER=$current NEXT=$next"
if [[ "$current" != "active" || "$next" != *"2026-10-27 03:05"* ]]; then
  echo "HOLD_STAGE11_NEXT_TIMER_NOT_EXPECTED"; exit 2
fi
path="$(mktemp /tmp/v5-oct26-only.XXXXXXXX.py)"
trap 'rm -f -- "$path"' EXIT
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
 "https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/4c2e6fdb2c906aae4977c959b45c6086f97c4045/deploy/conoha/v5_oct26_only_twelve_family_sync_20261027.py" \
 -o "$path"
chmod 0644 "$path"
/opt/boat-ai-v5-venv/bin/python - "$path" <<'PY'
import ast, pathlib, sys
ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print("V5_OCT26_ONLY_SCRIPT_SYNTAX_OK")
PY
echo "=== OCT26 12-FAMILY PREVIEW READ ONLY ==="
runuser -u postgres -- env DATABASE_URL=postgresql:///railway \
 /opt/boat-ai-v5-venv/bin/python "$path"
echo "=== OCT26 ONLY 12-FAMILY ATOMIC INSERT MISSING ==="
out="$(runuser -u postgres -- env DATABASE_URL=postgresql:///railway \
 V5_OCT26_ONLY_SYNC_APPROVED=YES V5_MIDNIGHT_CATCHUP_CONFIRMED=YES \
 /opt/boat-ai-v5-venv/bin/python "$path" --apply)"
printf "%s\n" "$out"
if [[ "$out" != *"V5_OCT26_ONLY_12_FAMILIES_COMMITTED_NO_LEGACY_WRITES_NO_DELETE_NO_BUY"* ]]; then
 echo "HOLD_OCT26_PARITY_NOT_COMMITTED_ONE_SHOT_KEPT"; exit 3
fi
if ! grep -q "^OCT26_VERIFIED|results|inserted=[0-9]*|rows=[1-9][0-9]*" <<< "$out"; then
 echo "HOLD_NO_OCT26_RESULT_ROWS_ONE_SHOT_KEPT"; exit 3
fi
for name in entry_snapshots exhibition_snapshots odds_snapshots weather_snapshots race_condition_snapshots racer_condition_snapshots; do
 if ! grep -q "^OCT26_VERIFIED|$name|inserted=[0-9]*|rows=[1-9][0-9]*" <<< "$out"; then
   echo "HOLD_NONEMPTY_SNAPSHOT_MISSING_$name_ONE_SHOT_KEPT"; exit 3
 fi
done
echo "=== RETIRE ONLY OLD ONE-TIME 03:05 FULL-HISTORY DELTA TIMER ==="
if [[ "$(date +%Y%m%d%H%M)" > "202610270259" ]]; then
 echo "HOLD_TOO_LATE_TO_RETIRE_TIMER_MANUALLY_CHECK"; exit 3
fi
current="$(systemctl show "$timer" -p ActiveState --value 2>/dev/null || true)"
next="$(systemctl show "$timer" -p NextElapseUSecRealtime --value 2>/dev/null || true)"
if [[ "$current" != "active" || "$next" != *"2026-10-27 03:05"* ]]; then
 echo "HOLD_TIMER_CHANGED_NO_STOP_REVIEW_REQUIRED"; exit 3
fi
systemctl stop "$timer"
remaining="$(systemctl show "$timer" -p ActiveState --value 2>/dev/null || true)"
if [[ "$remaining" == "active" ]]; then
 echo "HOLD_TIMER_STILL_ACTIVE_NEEDS_CHECK"; exit 3
fi
echo "V5_OCT26_ONLY_SYNC_CONFIRMED_AND_0305_ONE_SHOT_TIMER_RETIRED"
echo "LEGACY_COLLECTORS_STILL_ON_AND_NO_OLD_TABLE_DELETION_BUY_OFF"
