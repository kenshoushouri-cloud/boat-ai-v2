#!/usr/bin/env bash
# Preview first. Optional explicit INSERT-only one-race V5 stage canary.
# No old-table writes, timers, or BUY; requires post-03:05 success.
set -euo pipefail
umask 077
export TZ=Asia/Tokyo
[[ "$(id -u)" == "0" ]] || { echo "HOLD_ROOT_REQUIRED"; exit 2; }
[[ "$(date +%Y%m%d)" == "20261027" ]] || { echo "HOLD_OCT27_ONLY"; exit 2; }
PIN="e7625e53792fd1e7a7899d1bb7dd3f65f433cdef"
[[ "$(readlink -f /opt/boat-ai-v5-native/current)" == "/opt/boat-ai-v5-native/releases/$PIN" ]] || { echo "HOLD_NATIVE_PIN_MISMATCH"; exit 2; }
[[ -x /opt/boat-ai-v5-venv/bin/python && -f /opt/boat-ai-v5/repair_month_all_pg.py ]] || { echo "HOLD_NATIVE_PARSER_OR_PYTHON_MISSING"; exit 2; }
for unit in boat-v5-stage11-delta-20261027-recovery.timer boat-v5-stage11-delta-20261027-recovery.service; do
 state="$(systemctl is-active "$unit" 2>/dev/null || true)"
 [[ "$state" != "active" && "$state" != "activating" ]] || { echo "HOLD_STAGE11_ACTIVE"; exit 2; }
done
journal="$(journalctl -u boat-v5-stage11-delta-20261027-recovery.service --since "2026-10-27 03:00:00" --until "2026-10-27 06:00:00" --no-pager -o cat 2>/dev/null || true)"
grep -q "STAGE12_DELTA_SNAPSHOT_PASS families=11" <<< "$journal" || { echo "HOLD_STAGE11_NO_PASS"; exit 2; }
if grep -Eq "STAGE12_DELTA_HOLD|HOLD_" <<< "$journal"; then echo "HOLD_STAGE11_JOURNAL_ERROR"; exit 2; fi
run=(runuser -u postgres -- env DATABASE_URL=postgresql:///railway PYTHONPATH=/opt/boat-ai-v5-native/current:/opt/boat-ai-v5 BUY_ENABLED=0 AUTO_BUY=0 ENABLE_PURCHASE=0 /opt/boat-ai-v5-venv/bin/python -m v5.native_official_stage_canary --day 20261027 --max-venues 3)
echo "V5_NATIVE_CORE_PREVIEW_BEGIN_NO_DB_NO_WRITES_NO_BUY"
preview="$("${run[@]}")"
printf "%s\n" "$preview"
grep -q "V5_NATIVE_STAGE_OFFICIAL_VALIDATED race=20261027_" <<< "$preview" || { echo "HOLD_OFFICIAL_PREVIEW_NOT_VALID"; exit 2; }
grep -q "V5_NATIVE_STAGE_PREVIEW_NO_DB_NO_WRITES_NO_BUY" <<< "$preview" || { echo "HOLD_PREVIEW_INCOMPLETE"; exit 2; }
echo "V5_NATIVE_ONE_RACE_PREVIEW_PASS"
if [[ "${V5_ONE_RACE_STAGE_CANARY_APPROVED:-NO}" != "YES" ]]; then
 echo "PREVIEW_ONLY_NO_STAGE_WRITES_NO_OLD_STOP_NO_TIMERS"; exit 0
fi
echo "V5_NATIVE_ONE_RACE_CORE_STAGE_CANARY_BEGIN"
runuser -u postgres -- env DATABASE_URL=postgresql:///railway \
 PYTHONPATH=/opt/boat-ai-v5-native/current:/opt/boat-ai-v5 \
 V5_NATIVE_CORE_STAGE_WRITE_APPROVED=YES V5_SHARED_PRIMARY_MODE=CANARY \
 CONFIRM_V5_SHARED_PRIMARY_CANARY=YES CONFIRM_LEGACY_WRITES_SEPARATELY=YES \
 V5_STAGE_DELTA_JOURNAL_VERIFIED=YES BUY_ENABLED=0 AUTO_BUY=0 ENABLE_PURCHASE=0 \
 /opt/boat-ai-v5-venv/bin/python -m v5.native_official_stage_canary \
 --day 20261027 --max-venues 3 --apply
echo "V5_NATIVE_CORE_CANARY_RETURNED_VERIFY_INSERT_COUNTS"
echo "INSERT_COUNT_ZERO_MEANS_STAGE_ALREADY_HAD_ROW_NOT_NEW_WRITE_PROOF"
echo "NO_OLD_STOP_NO_NATIVE_TIMERS_ENABLED_NO_DATA_DELETE_NO_BUY"
