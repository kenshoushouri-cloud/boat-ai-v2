#!/usr/bin/env bash
# Only synthetic Python unit tests. No DB/network collector access, no timer
# or service operations, no BUY. Downloads pinned public GitHub source into
# one temporary directory then removes it. Uses stdlib unittest only.
set -euo pipefail
umask 077
repo="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/690ab7beab6eb02e5d9b8dcddda22fb92f33fb18"
tmp="$(mktemp -d /tmp/boat-v5-synthetic-unit.XXXXXXXX)"
trap 'rm -rf -- "$tmp"' EXIT

files=(
  v5/entry_quality_policy.py
  v5/offline_asof_eligibility.py
  v5/offline_mainline_inference.py
  v5/offline_paper_quality_bridge.py
  tests/test_v5_entry_quality_policy.py
  tests/test_v5_offline_paper_quality_bridge.py
)
echo "V5_SYNTHETIC_UNIT_TEST_START pin=690ab7beab6eb02e5d9b8dcddda22fb92f33fb18 files=${#files[@]} DB=NO LIVE_TIMER=NO BUY=OFF"
for f in "${files[@]}"; do
  case "$f" in v5/*.py|tests/*.py) ;; *) echo "UNSAFE_PATH_HOLD"; exit 90;; esac
  mkdir -p -- "$tmp/${f%/*}"
  curl -fsSL --connect-timeout 8 --max-time 30 --retry 1 \
       "$repo/$f" -o "$tmp/$f"
  test -s "$tmp/$f" || { echo "EMPTY_SOURCE_HOLD=$f"; exit 91; }
done
cd -- "$tmp"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
PYTHONPATH="$tmp" python3 -B -m unittest discover -s "$tmp/tests" -p 'test_v5_*quality*.py' -v
echo "V5_SYNTHETIC_UNIT_TEST_PASS DB=NO DB_WRITES=NO COLLECTOR_UNTOUCHED=YES BUY=OFF"
