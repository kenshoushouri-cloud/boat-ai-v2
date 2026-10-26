#!/usr/bin/env bash
# TEMP-only V5 native collector suite, NO DB/HTTP/live config/writes/BUY.
set -euo pipefail
umask 077
REF="e7625e53792fd1e7a7899d1bb7dd3f65f433cdef"
BASE="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/$REF"
work="$(mktemp -d /tmp/v5-native-validation.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/v5" "$work/tests"
touch "$work/v5/__init__.py"
for path in \
  v5/native_core_day_runner.py \
  v5/native_realtime_due_runner.py \
  v5/native_results_catchup_stage.py \
  v5/native_official_stage_canary.py \
  v5/native_official_index_preview.py \
  v5/native_stage_race_entries_pg.py \
  v5/native_official_realtime_stage_pg.py \
  official_odds3t_parser.py \
  tests/test_v5_native_stage_race_entries_pg.py \
  tests/test_v5_native_official_index_preview.py \
  tests/test_v5_native_official_stage_canary.py \
  tests/test_v5_native_official_realtime_stage_pg.py \
  tests/test_v5_native_transition_20261027.py; do
  mkdir -p "$work/$(dirname "$path")"
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
    "$BASE/$path" -o "$work/$path"
done
echo "V5_NATIVE_FULL_TRANSITION_OFFLINE_TEST_BEGIN_NO_DB_NO_HTTP_NO_WRITES"
(
 cd "$work"
 env -u DATABASE_URL -u V5_NATIVE_CORE_STAGE_WRITE_APPROVED \
   -u V5_NATIVE_REALTIME_STAGE_APPROVED -u V5_NATIVE_RESULTS_STAGE_APPROVED \
   -u V5_SHARED_PRIMARY_MODE -u CONFIRM_V5_SHARED_PRIMARY_CANARY \
   -u CONFIRM_LEGACY_WRITES_SEPARATELY -u V5_STAGE_DELTA_JOURNAL_VERIFIED \
   PYTHONPATH="$work" PYTHONDONTWRITEBYTECODE=1 \
   python3 -m unittest discover -s tests -p 'test_v5_native_*.py' -v
)
echo "V5_NATIVE_FULL_TRANSITION_OFFLINE_PASS_NO_DB_NO_HTTP_NO_TIMERS_NO_BUY"
