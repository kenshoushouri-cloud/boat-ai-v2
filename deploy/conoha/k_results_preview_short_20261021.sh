#!/usr/bin/env bash
# Read-only preview of the next 24 standard missing K results on 2026-10-08.
set -euo pipefail
cd /opt/boat-ai-v5
echo "=== PYTHON SYNTAX CHECK ==="
/opt/boat-ai-v5-venv/bin/python -c 'import ast,pathlib; ast.parse(pathlib.Path("deploy/conoha/k_missing_results_bounded_20261021.py").read_text())'
echo "=== RESULTS NEXT 24 PREVIEW ==="
nice -n 10 runuser -u postgres -- env \
  HTTP_TIMEOUT=20 HTTP_MAX_RETRIES=0 \
  /opt/boat-ai-v5-venv/bin/python \
  deploy/conoha/k_missing_results_bounded_20261021.py \
  --day 2026-10-08 --expected-results 1 --limit 24
echo "NEXT_24_RESULTS_PREVIEW_DONE_NO_DB_WRITES"
