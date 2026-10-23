#!/usr/bin/env bash
# Safe isolated Python tests only; no DB or cloud operations.
set -euo pipefail
REPO=/opt/boat-ai-v5
[[ -d "$REPO/.git" ]] || { echo "STOP: repository not found"; exit 1; }
TMP="$(mktemp -d /tmp/boat-stage-test-XXXXXXXX)"
trap 'rm -rf -- "$TMP"' EXIT
for p in boat_shared_storage_contract.py docs/BOAT_SHARED_13_SOURCE_ROUTE_MANIFEST_20261023.json deploy/conoha/boat_shared_staging_delta_plan_offline.py tests/test_boat_shared_staging_delta_plan_offline.py; do
  mkdir -p "$TMP/$(dirname "$p")"
  git -C "$REPO" show "origin/main:$p" > "$TMP/$p"
done
cd "$TMP"
echo "ISOLATED_OFFLINE_STAGE_TESTS_BEGIN"
env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p test_boat_shared_staging_delta_plan_offline.py -v
env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 python3 -B -m deploy.conoha.boat_shared_staging_delta_plan_offline > /dev/null
echo "OFFLINE_STAGE_AND_COMPLETE_KEY_DELTA_TESTS_PASS_NO_DB_NO_BUY"
