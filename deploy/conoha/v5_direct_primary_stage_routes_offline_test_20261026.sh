#!/usr/bin/env bash
# Offline (except fetching immutable GitHub source) route contract safety test.
# No collector configuration, service, database, production repo or prediction changes.
set -euo pipefail
umask 077
SHA="61d8f1c20b8f92fbcab8f18e706b501d8f8f3b66"
ROOT="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/${SHA}"
work="$(mktemp -d /tmp/v5-route-test.XXXXXXXX)" || exit 1
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/v5" "$work/tests"
touch "$work/v5/__init__.py"
for file in \
  boat_shared_storage_contract.py \
  v5/offline_stage_batch_plan.py \
  v5/direct_shared_primary_routes.py \
  v5_daily_table_routes.py \
  v5_realtime_table_routes.py \
  tests/test_v5_direct_shared_primary_routes.py
do
  echo "FETCHED_ROUTE_TEST_FILE=${file}"
  curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
    --connect-timeout 8 --max-time 15 "${ROOT}/${file}" -o "$work/${file}"
done
echo "V5_DIRECT_ROUTE_OFFLINE_TEST_BEGIN_NO_DB_NO_HTTP_COLLECTOR_NO_WRITES"
(
 cd "$work"
 env -u DATABASE_URL \
     -u V5_SHARED_PRIMARY_MODE \
     -u CONFIRM_V5_SHARED_PRIMARY_CANARY \
     -u CONFIRM_LEGACY_WRITES_SEPARATELY \
     PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$work" \
     python3 -m unittest discover -s tests \
       -p test_v5_direct_shared_primary_routes.py -v
)
echo "V5_DIRECT_ROUTE_OFFLINE_TEST_PASS_NO_DB_NO_LIVE_CONFIG_NO_BUY"
