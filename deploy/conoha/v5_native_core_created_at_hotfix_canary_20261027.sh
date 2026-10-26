#!/usr/bin/env bash
# Repair V5 official core stage created_at and negative bigint entries.id.
# Runs corrected source in a temporary overlay, never edits installed release.
# PREVIEW default; gated apply writes one 2026-10-27 official race/6 entries only.
set -euo pipefail
umask 077
export TZ=Asia/Tokyo
[[ "$(id -u)" == "0" ]] || { echo "HOLD_ROOT_ONLY"; exit 2; }
[[ "$(date +%Y%m%d)" == "20261027" ]] || { echo "HOLD_OCT27_ONLY"; exit 2; }
RELEASE="/opt/boat-ai-v5-native/releases/e7625e53792fd1e7a7899d1bb7dd3f65f433cdef"
[[ "$(readlink -f /opt/boat-ai-v5-native/current)" == "$RELEASE" ]] || { echo "HOLD_NATIVE_RELEASE_PIN_CHANGED"; exit 2; }
[[ -x /opt/boat-ai-v5-venv/bin/python ]] || { echo "HOLD_VENV_MISSING"; exit 2; }
[[ -f /opt/boat-ai-v5/repair_month_all_pg.py ]] || { echo "HOLD_OFFICIAL_PARSER_MISSING"; exit 2; }
work="$(mktemp -d /tmp/v5-native-core-created-at.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
cp -a "$RELEASE/." "$work/"
mkdir -p "$work/tests"
chmod 0755 "$work" "$work/v5" "$work/tests"
REF="056503ca3f774c86156c563e64fe08d8f7d4193c"
URL="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/$REF"
for src in v5/native_stage_race_entries_pg.py tests/test_v5_native_stage_race_entries_pg.py; do
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
    "$URL/$src" -o "$work/$src"
  chmod 0644 "$work/$src"
done
echo "=== V5 CREATED_AT HOTFIX CORE OFFLINE TESTS, NO DB/HTTP ==="
(
 cd "$work"
 env -u DATABASE_URL -u V5_NATIVE_CORE_STAGE_WRITE_APPROVED \
     -u V5_STAGE_DELTA_JOURNAL_VERIFIED \
     PYTHONPATH="$work" PYTHONDONTWRITEBYTECODE=1 \
     python3 -m unittest discover -s tests \
         -p test_v5_native_stage_race_entries_pg.py -v
)
echo "V5_CORE_CREATED_AT_AND_ENTRY_ID_OFFLINE_PASS"
echo "=== VERIFIED 03:05 STAGE11 JOURNAL, READ ONLY ==="
for unit in boat-v5-stage11-delta-20261027-recovery.timer boat-v5-stage11-delta-20261027-recovery.service; do
  state="$(systemctl is-active "$unit" 2>/dev/null || true)"
  [[ "$state" != "active" && "$state" != "activating" ]] || { echo "HOLD_STAGE11_CURRENTLY_ACTIVE"; exit 2; }
done
journal="$(journalctl -u boat-v5-stage11-delta-20261027-recovery.service --since "2026-10-27 03:00:00" --until "2026-10-27 06:00:00" --no-pager -o cat 2>/dev/null || true)"
grep -q "STAGE12_DELTA_SNAPSHOT_PASS families=11" <<< "$journal" || { echo "HOLD_0305_SYNC_NOT_PROVEN"; exit 2; }
if grep -Eq "STAGE12_DELTA_HOLD|HOLD_" <<< "$journal"; then echo "HOLD_0305_SYNC_ERROR"; exit 2; fi
echo "V5_CREATED_AT_STAGE11_PASS"
echo "=== STAGE RACES/ENTRIES NOT-NULL CATALOG, READ ONLY ==="
runuser -u postgres -- psql -X -A -F "|" -P pager=off -v ON_ERROR_STOP=1 -d railway <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='5000ms';
SELECT n.nspname||'.'||c.relname AS stage_table,a.attname AS col,
       format_type(a.atttypid,a.atttypmod) AS datatype,
       a.attnotnull AS required,a.atthasdef AS has_default
  FROM pg_attribute a
  JOIN pg_class c ON c.oid=a.attrelid
  JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='boat_data_stage' AND c.relname IN ('races','entries')
   AND a.attnum>0 AND NOT a.attisdropped AND a.attnotnull
 ORDER BY c.relname,a.attnum;
ROLLBACK;
SQL
echo "=== V5 OFFICIAL 1R HOTFIX PREVIEW, NO DB WRITES ==="
common=(DATABASE_URL=postgresql:///railway PYTHONPATH="$work:/opt/boat-ai-v5" BUY_ENABLED=0 AUTO_BUY=0 ENABLE_PURCHASE=0)
preview="$(runuser -u postgres -- env "${common[@]}" \
 /opt/boat-ai-v5-venv/bin/python -m v5.native_official_stage_canary \
 --day 20261027 --max-venues 3)"
printf "%s\n" "$preview"
grep -q "V5_NATIVE_STAGE_OFFICIAL_VALIDATED race=20261027_" <<< "$preview" || { echo "HOLD_OFFICIAL_PREVIEW_NO_RACE"; exit 2; }
grep -q "V5_NATIVE_STAGE_PREVIEW_NO_DB_NO_WRITES_NO_BUY" <<< "$preview" || { echo "HOLD_PREVIEW_NOT_COMPLETE"; exit 2; }
echo "V5_CORE_CREATED_AT_ENTRY_ID_HOTFIX_PREVIEW_PASS_NO_WRITES"
if [[ "${V5_CREATED_AT_CANARY_APPLY_APPROVED:-NO}" != "YES" ]]; then
  echo "V5_CREATED_AT_HOTFIX_PREVIEW_ONLY_NO_TIMERS_NO_OLD_STOP"; exit 0
fi
echo "=== V5 NATIVE CORE HOTFIX ONE-RACE INSERT-ONLY CANARY ==="
runuser -u postgres -- env "${common[@]}" \
 V5_NATIVE_CORE_STAGE_WRITE_APPROVED=YES V5_SHARED_PRIMARY_MODE=CANARY \
 CONFIRM_V5_SHARED_PRIMARY_CANARY=YES CONFIRM_LEGACY_WRITES_SEPARATELY=YES \
 V5_STAGE_DELTA_JOURNAL_VERIFIED=YES \
 /opt/boat-ai-v5-venv/bin/python -m v5.native_official_stage_canary \
 --day 20261027 --max-venues 3 --apply
echo "V5_CREATED_AT_HOTFIX_CANARY_RETURNED_CHECK_RACE_AND_ENTRY_INSERT_COUNTS"
echo "NO_NEW_NATIVE_TIMER_ACTIVATION_NO_LEGACY_STOP_NO_DATA_DELETE_NO_BUY"
