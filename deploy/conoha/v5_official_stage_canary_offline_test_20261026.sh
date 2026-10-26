#!/usr/bin/env bash
# Native official index -> V5 physical stage single-race canary contracts.
# OFFLINE TEST ONLY: no website, PostgreSQL, collector, systemd or BUY.
set -euo pipefail
umask 077
REPO_REF="9faac47d6e4e71c3308214abcbede2e81f519452"
ROOT="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/${REPO_REF}"
work="$(mktemp -d /tmp/v5-official-stage-canary.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/v5" "$work/tests"
touch "$work/v5/__init__.py"
for src in \
  v5/native_official_stage_canary.py \
  v5/native_official_index_preview.py \
  v5/native_stage_race_entries_pg.py \
  tests/test_v5_native_official_stage_canary.py; do
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
    "${ROOT}/${src}" -o "$work/$src"
done
echo "V5_OFFICIAL_STAGE_CANARY_OFFLINE_TEST_BEGIN"
(
 cd "$work"
 env -u DATABASE_URL -u V5_NATIVE_CORE_STAGE_WRITE_APPROVED \
     -u V5_SHARED_PRIMARY_MODE -u CONFIRM_V5_SHARED_PRIMARY_CANARY \
     -u CONFIRM_LEGACY_WRITES_SEPARATELY -u V5_STAGE_DELTA_JOURNAL_VERIFIED \
     PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$work" \
     python3 -m unittest discover -s tests -p test_v5_native_official_stage_canary.py -v
)
echo "V5_OFFICIAL_STAGE_CANARY_OFFLINE_PASS_NO_DB_NO_HTTP_NO_WRITES_NO_BUY"
