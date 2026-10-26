#!/usr/bin/env bash
# GitHub-pinned V5 direct official index discovery + one-race PREVIEW.
# No legacy DB reads, no DB write, no systemd modification, no buy.
set -euo pipefail
umask 077
REF="1c1ec4a6439a227d58349cf383161f6b57a75e8b"
BASE="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/${REF}"
work="$(mktemp -d /tmp/v5-direct-official-index.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/v5" "$work/tests"
touch "$work/v5/__init__.py"
for src in v5/native_official_index_preview.py v5/native_stage_race_entries_pg.py tests/test_v5_native_official_index_preview.py; do
  mkdir -p "$work/$(dirname "$src")"
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
    "${BASE}/${src}" -o "$work/${src}"
done
echo "V5_OFFICIAL_INDEX_OFFLINE_TEST_START_NO_DB"
(
 cd "$work"
 env -u DATABASE_URL -u V5_NATIVE_CORE_STAGE_WRITE_APPROVED \
    -u V5_SHARED_PRIMARY_MODE -u CONFIRM_V5_SHARED_PRIMARY_CANARY \
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$work" \
    python3 -m unittest discover -s tests -p test_v5_native_official_index_preview.py -v
)
echo "V5_OFFICIAL_INDEX_OFFLINE_TEST_PASS"
if [[ ! -x /opt/boat-ai-v5-venv/bin/python || ! -f /opt/boat-ai-v5/repair_month_all_pg.py ]]; then
  echo "HOLD_V5_LOCAL_VENV_OR_OFFICIAL_RACELIST_PARSER_MISSING"
  exit 2
fi
echo "V5_OFFICIAL_DIRECT_PREVIEW_START_NO_LEGACY_DB_NO_WRITES"
cd "$work"
env -u DATABASE_URL -u V5_NATIVE_CORE_STAGE_WRITE_APPROVED \
  -u V5_SHARED_PRIMARY_MODE -u CONFIRM_V5_SHARED_PRIMARY_CANARY \
  -u CONFIRM_LEGACY_WRITES_SEPARATELY -u BUY_ENABLED -u AUTO_BUY -u ENABLE_PURCHASE \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$work:/opt/boat-ai-v5" \
  /opt/boat-ai-v5-venv/bin/python -m v5.native_official_index_preview --max-venues 3
echo "V5_OFFICIAL_DIRECT_PREVIEW_END_NO_LEGACY_DB_NO_WRITES_NO_BUY"
