#!/usr/bin/env bash
# Isolated real OFFICIAL racelist preview. One future race maximum.
# Reads local public.v2_races only to choose race_id; official content from direct HTTPS.
# No database writes, no scheduled changes, no BUY.
set -euo pipefail
umask 077
if [[ "$(id -u)" != "0" ]]; then echo HOLD_RUN_AS_ROOT; exit 2; fi
if [[ ! -x /opt/boat-ai-v5-venv/bin/python || ! -f /opt/boat-ai-v5/repair_month_all_pg.py ]]; then
  echo HOLD_LOCAL_PARSER_OR_VENV_MISSING; exit 2
fi
echo V5_SINGLE_OFFICIAL_PREVIEW_BEGIN_READ_ONLY
rid="$(runuser -u postgres -- psql -XAt -v ON_ERROR_STOP=1 -d railway <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='500ms';
SELECT race_id FROM public.v2_races
 WHERE race_date BETWEEN DATE '2026-10-27' AND DATE '2026-10-27'
   AND deadline_at IS NOT NULL
   AND deadline_at::timestamptz > now() + interval '10 minutes'
 ORDER BY deadline_at::timestamptz,race_id LIMIT 1;
ROLLBACK;
SQL
)"
rid="$(printf '%s\n' "$rid" | grep -E '^20261027_(0[1-9]|1[0-9]|2[0-4])_(0[1-9]|1[0-2])$' | head -n 1 || true)"
if [[ -z "$rid" ]]; then
  echo HOLD_NO_FUTURE_RACE_IN_LEGACY_METADATA_NO_HTTP_NO_WRITES
  exit 0
fi
echo "V5_PREVIEW_TARGET_RACE=$rid"
script="$(mktemp /tmp/v5-native-core-preview.XXXXXXXX.py)"
trap 'rm -f -- "$script"' EXIT
chmod 0644 "$script"
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
  https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/431655ae77ab592b0a4aecba781a1b3f56ad61e4/v5/native_stage_race_entries_pg.py \
  -o "$script"
runuser -u postgres -- env -u V5_NATIVE_CORE_STAGE_WRITE_APPROVED \
  -u V5_SHARED_PRIMARY_MODE -u CONFIRM_V5_SHARED_PRIMARY_CANARY \
  PYTHONPATH=/opt/boat-ai-v5 PYTHONDONTWRITEBYTECODE=1 \
  /opt/boat-ai-v5-venv/bin/python "$script" --race-id "$rid"
echo V5_SINGLE_OFFICIAL_PREVIEW_FINISHED_NO_DB_WRITES_NO_BUY
