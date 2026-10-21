#!/usr/bin/env bash
# Detached, finite Oct 08 72-result repair: three proven 24-row INSERT-only batches.
# No cron, no persistent service; only a one-shot systemd-run transient unit.
# Existing result UPDATE/DELETE never allowed. Never auto-retry on failure.
set -euo pipefail
umask 077
cd /opt/boat-ai-v5
UNIT=boat-v5-kresults-72-20261021
SELF=/opt/boat-ai-v5/deploy/conoha/k_results_background72_20261021.sh
DIR=/root/boat-v5-backups
OLD_BAK="$DIR/k_results_preinsert_20261021_193138.dump"
MARK="$DIR/.oct08_results_bg72_20261021_launched"
[[ $(id -u) == 0 ]] || { echo "STOP: must run as root"; exit 1; }

db_state() {
  runuser -u postgres -- psql -X -A -t -v ON_ERROR_STOP=1 -d railway -c "
    BEGIN READ ONLY;
    SELECT
      (SELECT count(*) FROM public.v2_races WHERE race_id >= '20261008_' AND race_id < '20261009_')::text || ':' ||
      (SELECT count(*) FROM public.v2_race_entries WHERE race_id >= '20261008_' AND race_id < '20261009_')::text || ':' ||
      (SELECT count(*) FROM public.v2_results WHERE race_id >= '20261008_' AND race_id < '20261009_')::text;
    COMMIT;" | grep -E '^[0-9]+:[0-9]+:[0-9]+$'
}

backup_gate() {
  [[ -s "$OLD_BAK" && -s "$OLD_BAK.sha256" ]] || {
    echo "STOP: known SHA256/TOC backup missing"; exit 1;
  }
  sha256sum -c "$OLD_BAK.sha256"
  toc="$(pg_restore --list "$OLD_BAK")"
  for t in v2_races v2_race_entries v2_results v2_result_entries; do
    grep -Eq "TABLE DATA public ${t} " <<<"$toc" || {
      echo "STOP: backup missing $t"; exit 1;
    }
  done
  echo "EXISTING_BACKUP_SHA_TOC_OK"
}

if [[ "${1:-start}" == "worker" ]]; then
  echo "BG_WORKER_STARTED $(date -Is)"
  backup_gate
  [[ "$(db_state)" == "144:864:25" ]] || {
    echo "STOP: unexpected DB state before fresh backup"; exit 1;
  }
  echo "=== FRESH BACKUP AFTER FIRST 25 RESULTS ==="
  bash /opt/boat-ai-v5/deploy/conoha/backup_k_results_before_insert_20261021.sh
  echo "=== GUARDED BATCHES ==="
  for expected in 25 49 73; do
    actual="$(db_state)"
    echo "BATCH_BEFORE=$actual EXPECTED=144:864:$expected"
    [[ "$actual" == "144:864:$expected" ]] || {
      echo "STOP: unexpected DB state before batch"; exit 1;
    }
    nice -n 10 runuser -u postgres -- env \
      CONFIRM_V5_RESULTS_INSERT=YES HTTP_TIMEOUT=20 HTTP_MAX_RETRIES=0 \
      /opt/boat-ai-v5-venv/bin/python \
      deploy/conoha/k_missing_results_bounded_20261021.py \
      --day 2026-10-08 --expected-results "$expected" --limit 24 --apply
    after="$(db_state)"
    next=$((expected + 24))
    echo "BATCH_AFTER=$after EXPECTED=144:864:$next"
    [[ "$after" == "144:864:$next" ]] || {
      echo "STOP: batch count mismatch; do not rerun"; exit 1;
    }
    echo "BG_24_RESULT_BATCH_PASS count=$next"
  done
  [[ "$(db_state)" == "144:864:97" ]] || {
    echo "STOP: final DB count mismatch"; exit 1;
  }
  echo "OCT08_BG72_COMPLETE result_rows=97 added=72"
  echo "HISTORICAL_RETRIEVAL_NOT_PREDECISION"
  exit 0
fi

[[ "${1:-start}" == "start" ]] || { echo "STOP: use start or worker"; exit 1; }
command -v systemd-run >/dev/null || { echo "STOP: systemd-run unavailable"; exit 1; }
command -v systemctl >/dev/null || { echo "STOP: systemctl unavailable"; exit 1; }
[[ -s "$SELF" ]] || { echo "STOP: worker file missing"; exit 1; }
# Syntax-check scripts without importing or modifying Python modules.
bash -n "$SELF"
bash -n /opt/boat-ai-v5/deploy/conoha/backup_k_results_before_insert_20261021.sh
/opt/boat-ai-v5-venv/bin/python -c 'import ast,pathlib; ast.parse(pathlib.Path("deploy/conoha/k_missing_results_bounded_20261021.py").read_text())'
backup_gate
BEFORE="$(db_state)"
echo "DB_BEFORE=$BEFORE EXPECTED=144:864:25"
[[ "$BEFORE" == "144:864:25" ]] || {
  echo "STOP: DB no longer at validated 25-result checkpoint"; exit 1;
}
[[ ! -e "$MARK" ]] || { echo "STOP: this background job was already launched; inspect logs"; exit 1; }
# Create marker atomically; intentional no automatic retries even if terminal crashes.
( set -C; printf '%s\n' "requested_at=$(date -Is)" > "$MARK" ) || {
  echo "STOP: marker exists or creation failed"; exit 1;
}
echo "=== START DETACHED UNIT ==="
if ! systemd-run --unit="$UNIT" --collect --no-block \
  --property=Nice=10 --property=CPUQuota=50% \
  --property=MemoryMax=850M --property=Restart=no \
  /bin/bash "$SELF" worker; then
  echo "STOP: unit start failed; marker retained to prevent accidental retry"
  exit 1
fi
echo "BG72_LAUNCHED_UNIT=$UNIT"
echo "STATUS: journalctl -u $UNIT -n 30 --no-pager"
echo "This confirms launch, not successful completion."
