#!/usr/bin/env bash
# Synthetic-only offline tests. No PostgreSQL, DB writes, model scoring,
# timers, collectors, filesystem outside a temporary folder, or BUY.
set -euo pipefail
umask 077
base="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/ad8e8a1b3297ae0392929b69bef83fd50f4fe476"
tmp="$(mktemp -d /tmp/boat-v5-view-unit.XXXXXXXX)"
trap 'rm -rf -- "$tmp"' EXIT
files=(v5/entry_quality_policy.py v5/offline_entry_view_adapter.py tests/test_v5_offline_entry_view_adapter.py)
echo "V5_VIEW_ADAPTER_TEST_START pin=ad8e8a1b3297ae0392929b69bef83fd50f4fe476 files=3 DB=NO TIMERS=UNCHANGED BUY=OFF"
for f in "${files[@]}"; do
  case "$f" in v5/*.py|tests/*.py) ;; *) echo "UNEXPECTED_SOURCE_HOLD"; exit 90;; esac
  mkdir -p -- "$tmp/${f%/*}"
  curl -fsSL --connect-timeout 8 --max-time 30 --retry 1 "$base/$f" -o "$tmp/$f"
  test -s "$tmp/$f" || { echo "EMPTY_SOURCE_HOLD $f"; exit 91; }
done
cd -- "$tmp"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH="$tmp" python3 -B -m unittest discover -s tests -p 'test_v5_offline_entry_view_adapter.py' -v
echo "V5_VIEW_ADAPTER_TEST_PASS DB=NO DB_WRITES=NO LIVE_COLLECTOR=UNTOUCHED BUY=OFF"
