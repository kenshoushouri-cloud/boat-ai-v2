#!/usr/bin/env bash
# One-shot guarded INSERT of the official trifecta-invalid result only.
# Creates/validates a fresh backup of all four protected tables first.
# Execute ONCE. On any error, inspect DB before attempting further action.
set -euo pipefail
umask 077
cd /opt/boat-ai-v5

RID=20261008_14_05
MARKER=/root/boat-v5-backups/.special_result_20261008_14_05_apply_once
PY=/opt/boat-ai-v5-venv/bin/python
PREVIEW=deploy/conoha/k_special_result_insert_preview_20261021.py
INSERT=deploy/conoha/k_special_result_insert_one_20261021.py
BACKUP_SCRIPT=deploy/conoha/backup_k_results_before_insert_20261021.sh

[[ "$(id -u)" == 0 ]] || { echo "STOP: run wrapper as root"; exit 1; }
[[ ! -e "$MARKER" ]] || { echo "STOP: marker exists, inspect current DB state; never rerun"; exit 1; }

# Abort if earlier jobs are active. Never restart or stop any service.
for unit in boat-v5-kresults-72-20261021.service boat-v5-kresults-192-20261021.service; do
  if systemctl is-active --quiet "$unit"; then
    echo "STOP: previous recovery service still active: $unit"; exit 1
  fi
done

echo "=== SYNTAX CHECK ==="
bash -n "$BACKUP_SCRIPT"
"$PY" -c 'import ast,pathlib; [ast.parse(pathlib.Path(x).read_text()) for x in ("deploy/conoha/k_special_result_insert_preview_20261021.py","deploy/conoha/k_special_result_insert_one_20261021.py")]'

echo "=== READ-ONLY OFFICIAL + DATABASE PREFLIGHT ==="
runuser -u postgres -- env HTTP_TIMEOUT=20 HTTP_MAX_RETRIES=0 \
  "$PY" "$PREVIEW"

echo "=== FRESH FOUR-TABLE BACKUP ==="
BACKUP_LOG="$(bash "$BACKUP_SCRIPT")"
printf '%s\n' "$BACKUP_LOG"
BACKUP="$(printf '%s\n' "$BACKUP_LOG" | sed -n 's/^FOUR_TABLE_FRESH_BACKUP_OK=//p' | tail -n 1)"
[[ "$BACKUP" == /root/boat-v5-backups/k_results_preinsert_*.dump ]] || {
  echo "STOP: unexpected backup path"; exit 1;
}
[[ -s "$BACKUP" && -s "$BACKUP.sha256" ]] || {
  echo "STOP: verified backup missing"; exit 1;
}
sha256sum -c "$BACKUP.sha256"
TOC="$(pg_restore --list "$BACKUP")"
for table in v2_races v2_race_entries v2_results v2_result_entries; do
  grep -Eq "TABLE DATA public $table " <<< "$TOC" || {
    echo "STOP: missing backup table $table"; exit 1;
  }
done
echo "FRESH_FOUR_TABLE_BACKUP_SHA_TOC_PASS=$BACKUP"

# Atomic marker remains on success, failure or mobile disconnection.
( set -C; printf 'started=%s\nbackup=%s\n' "$(date -Is)" "$BACKUP" > "$MARKER" ) || {
  echo "STOP: failed to acquire one-shot marker"; exit 1;
}

echo "=== APPLY EXACTLY ONE SPECIAL RESULT (INSERT-ONLY) ==="
nice -n 10 runuser -u postgres -- env \
  CONFIRM_V5_SPECIAL_RESULT_INSERT="$RID" \
  HTTP_TIMEOUT=20 HTTP_MAX_RETRIES=0 \
  "$PY" "$INSERT" --apply

echo "SPECIAL_RESULT_WRAPPER_COMPLETE"
echo "Do not rerun; audit downstream ROI filters before backtesting."
