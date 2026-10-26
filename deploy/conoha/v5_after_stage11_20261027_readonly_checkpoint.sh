#!/usr/bin/env bash
# 2026-10-27 after 06:00 JST: verify stage11 journal and run Oct stage QA.
# READ-ONLY: no DB writes, no service changes, no BUY, no new collections.
set -euo pipefail
export TZ=Asia/Tokyo
now="$(date +%Y%m%d%H%M)"
if [[ "$now" < "202610270600" ]]; then
  echo "HOLD_UNTIL_20261027_0600_JST"; exit 2
fi
unit="boat-v5-stage11-delta-20261027-recovery.service"
echo "V5_AFTER_STAGE11_READ_ONLY_CHECKPOINT_BEGIN"
systemctl show "$unit" --no-pager -p LoadState -p ActiveState -p Result \
  -p ExecMainStatus -p ExecMainStartTimestamp -p ExecMainExitTimestamp || true
log="$(journalctl -u "$unit" --since "2026-10-27 03:00:00" \
  --until "2026-10-27 06:00:00" --no-pager -o cat 2>/dev/null || true)"
if [[ -z "$log" ]]; then
  echo "HOLD_NO_RECOVERY_JOURNAL_CANNOT_CERTIFY_SYNC"; exit 3
fi
printf "%s\n" "$log" | \
  grep -E "DELTA_TABLE_COMMITTED|STAGE12_DELTA_SNAPSHOT_PASS|STAGE12_DELTA_HOLD|HOLD_" | \
  sed -E '/TOKEN|PASSWORD|SECRET|DATABASE_URL|postgres(ql)?:\/\//I s/.*/[REDACTED]/' | tail -n 32 || true
if printf "%s\n" "$log" | grep -Eq "STAGE12_DELTA_HOLD|HOLD_"; then
  echo "HOLD_STAGE_DELTA_ERROR_JOURNAL_NO_CANARY"; exit 3
fi
if ! printf "%s\n" "$log" | grep -q "DELTA_TABLE_COMMITTED entries"; then
  echo "HOLD_NO_ENTRIES_COMMIT_PROOF_NO_CANARY"; exit 3
fi
if ! printf "%s\n" "$log" | grep -q "STAGE12_DELTA_SNAPSHOT_PASS"; then
  echo "HOLD_INCOMPLETE_STAGE_DELTA_NO_CANARY"; exit 3
fi
echo "V5_STAGE11_JOURNAL_COMPLETION_MARKERS_FOUND_NOT_ASOF_PROOF"
if [[ ! -x /usr/sbin/runuser ]] && ! command -v runuser >/dev/null; then
  echo "HOLD_MISSING_RUNUSER"; exit 3
fi
work="$(mktemp /tmp/v5-stage-monthly.XXXXXXXX.sh)"
trap 'rm -f -- "$work"' EXIT
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
  https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/e7195fb9f933cb7b9a9840e03f35c4b7e7a51e80/deploy/conoha/v5_shared_stage_races_entries_monthly_batch_readonly_20261026.sh \
  -o "$work"
bash "$work" 2026-10 1
echo "V5_AFTER_STAGE11_READ_ONLY_CHECKPOINT_END_NO_DB_WRITES_NO_CANARY_NO_BUY"
