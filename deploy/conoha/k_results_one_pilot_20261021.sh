#!/usr/bin/env bash
# One-result historical INSERT pilot; requires previously verified 4-table backup.
set -euo pipefail
umask 077
cd /opt/boat-ai-v5
if [[ "$(id -u)" != "0" ]]; then
  echo "STOP: requires root for backup integrity gate"; exit 1
fi
BACKUP=/root/boat-v5-backups/k_results_preinsert_20261021_193138.dump
test -s "$BACKUP" && test -s "$BACKUP.sha256" || {
  echo "STOP: required fresh four-table backup missing"; exit 1
}
echo "=== BACKUP SHA256 CHECK ==="
sha256sum -c "$BACKUP.sha256"
echo "=== BACKUP TOC CHECK ==="
TOC="$(pg_restore --list "$BACKUP")"
for name in v2_races v2_race_entries v2_results v2_result_entries; do
  if ! grep -Eq "TABLE DATA public ${name} " <<< "$TOC"; then
    echo "STOP: backup missing $name"; exit 1
  fi
done
echo "=== PYTHON SYNTAX CHECK ==="
/opt/boat-ai-v5-venv/bin/python -c 'import ast,pathlib; ast.parse(pathlib.Path("deploy/conoha/k_missing_results_one_insert_20261021.py").read_text())'
echo "=== SINGLE RESULT INSERT (GUARDED) ==="
nice -n 10 runuser -u postgres -- env \
  CONFIRM_V5_RESULTS_INSERT=YES \
  HTTP_TIMEOUT=20 HTTP_MAX_RETRIES=0 \
  /opt/boat-ai-v5-venv/bin/python \
  deploy/conoha/k_missing_results_one_insert_20261021.py --apply
echo "RESULTS_SINGLE_PILOT_WRAPPER_DONE"
