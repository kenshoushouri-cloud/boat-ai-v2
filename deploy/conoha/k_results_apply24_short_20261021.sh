#!/usr/bin/env bash
# One approved 24-result batch, 2026-10-08 only. Never auto-rerun on failure.
set -euo pipefail
umask 077
cd /opt/boat-ai-v5
if [[ "$(id -u)" != 0 ]]; then
  echo "STOP: run as root for local backup verification"; exit 1
fi

BACKUP=/root/boat-v5-backups/k_results_preinsert_20261021_193138.dump
if [[ ! -s "$BACKUP" || ! -s "$BACKUP.sha256" ]]; then
  echo "STOP: required 4-table backup missing"; exit 1
fi
echo "=== VERIFIED BACKUP ==="
sha256sum -c "$BACKUP.sha256"
TOC="$(pg_restore --list "$BACKUP")"
for table in v2_races v2_race_entries v2_results v2_result_entries; do
  if ! grep -Eq "TABLE DATA public ${table} " <<<"$TOC"; then
    echo "STOP: backup has no TABLE DATA for $table"; exit 1
  fi
done

echo "=== PYTHON SYNTAX CHECK ==="
/opt/boat-ai-v5-venv/bin/python -c 'import ast,pathlib; ast.parse(pathlib.Path("deploy/conoha/k_missing_results_bounded_20261021.py").read_text())'

count_state() {
  runuser -u postgres -- psql -X -At -v ON_ERROR_STOP=1 -d railway -c "
    BEGIN READ ONLY;
    SELECT
      (SELECT count(*) FROM public.v2_races WHERE race_id >= '20261008_' AND race_id < '20261009_') || ':' ||
      (SELECT count(*) FROM public.v2_race_entries WHERE race_id >= '20261008_' AND race_id < '20261009_') || ':' ||
      (SELECT count(*) FROM public.v2_results WHERE race_id >= '20261008_' AND race_id < '20261009_');
    COMMIT;" | grep -E '^[0-9]+:[0-9]+:[0-9]+$'
}
BEFORE="$(count_state)"
echo "BEFORE=$BEFORE EXPECTED=144:864:1"
if [[ "$BEFORE" != "144:864:1" ]]; then
  echo "STOP: DB changed since preview; do not apply"; exit 1
fi

echo "=== GUARDED 24 RESULTS INSERT ==="
nice -n 10 runuser -u postgres -- env \
  CONFIRM_V5_RESULTS_INSERT=YES HTTP_TIMEOUT=20 HTTP_MAX_RETRIES=0 \
  /opt/boat-ai-v5-venv/bin/python \
  deploy/conoha/k_missing_results_bounded_20261021.py \
  --day 2026-10-08 --expected-results 1 --limit 24 --apply

AFTER="$(count_state)"
echo "AFTER=$AFTER EXPECTED=144:864:25"
if [[ "$AFTER" != "144:864:25" ]]; then
  echo "STOP: post-batch count mismatch; do not rerun"; exit 1
fi
echo "RESULTS_FIRST_24_APPLY_VERIFIED"
echo "HISTORICAL_RETRIEVAL_NOT_PREDECISION"
