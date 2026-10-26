#!/usr/bin/env bash
# Offline native V5 core collector safety tests. Fetch pinned GitHub code only.
# Does not connect PG or official site, execute collectors, alter systemd or BUY.
set -euo pipefail
umask 077
REF="431655ae77ab592b0a4aecba781a1b3f56ad61e4"
BASE="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/${REF}"
work="$(mktemp -d /tmp/v5-native-stage-test.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/v5" "$work/tests"
touch "$work/v5/__init__.py"
for name in v5/native_stage_race_entries_pg.py tests/test_v5_native_stage_race_entries_pg.py; do
  mkdir -p "$work/$(dirname "$name")"
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
    "${BASE}/${name}" -o "$work/${name}"
done
echo "V5_NATIVE_STAGE_CORE_OFFLINE_BEGIN_NO_DB_NO_COLLECTOR_NO_WRITES"
(
  cd "$work"
  env -u DATABASE_URL -u V5_NATIVE_CORE_STAGE_WRITE_APPROVED \
      -u V5_SHARED_PRIMARY_MODE -u CONFIRM_V5_SHARED_PRIMARY_CANARY \
      -u CONFIRM_LEGACY_WRITES_SEPARATELY \
      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$work" \
      python3 -m unittest discover -s tests \
        -p test_v5_native_stage_race_entries_pg.py -v
)
echo "V5_NATIVE_STAGE_CORE_OFFLINE_PASS_NO_DB_NO_SITE_NO_CUTOVER_NO_BUY"
