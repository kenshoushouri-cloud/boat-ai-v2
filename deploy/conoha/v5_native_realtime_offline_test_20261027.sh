#!/usr/bin/env bash
# Pinned V5 independent direct official realtime stage six-family tests.
# OFFLINE: no database, HTTP collector, systemd/timer edits, BUY.
set -euo pipefail
umask 077
REF="09dbb8658f1d7ff6d1065cc0386737863b332219"
BASE="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/${REF}"
work="$(mktemp -d /tmp/v5-direct-realtime.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/v5" "$work/tests"
touch "$work/v5/__init__.py"
for src in v5/native_official_realtime_stage_pg.py \
           v5/native_stage_race_entries_pg.py \
           official_odds3t_parser.py \
           tests/test_v5_native_official_realtime_stage_pg.py; do
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
    "${BASE}/${src}" -o "$work/$src"
done
echo "V5_NATIVE_REALTIME_OFFLINE_TEST_BEGIN_NO_DB_NO_SITE_NO_BUY"
(
  cd "$work"
  env -u DATABASE_URL -u V5_NATIVE_REALTIME_STAGE_APPROVED \
      -u V5_SHARED_PRIMARY_MODE -u CONFIRM_V5_SHARED_PRIMARY_CANARY \
      -u CONFIRM_LEGACY_WRITES_SEPARATELY -u V5_STAGE_DELTA_JOURNAL_VERIFIED \
      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$work" \
      python3 -m unittest discover -s tests \
        -p test_v5_native_official_realtime_stage_pg.py -v
)
echo "V5_NATIVE_REALTIME_OFFLINE_PASS_NO_DB_NO_HTTP_NO_WRITES_NO_BUY"
