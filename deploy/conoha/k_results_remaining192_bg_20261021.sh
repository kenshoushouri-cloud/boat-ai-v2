#!/usr/bin/env bash
# Finite one-shot background recovery of the remaining 192 STANDARD results.
# Four fixed dates only, INSERT-only. Never retries, never alters cron.
# Historical results MUST NOT enter pre-deadline model evidence.
set -euo pipefail
umask 077
cd /opt/boat-ai-v5
UNIT=boat-v5-kresults-192-20261021
SELF=/opt/boat-ai-v5/deploy/conoha/k_results_remaining192_bg_20261021.sh
DIR=/root/boat-v5-backups
OLD_BACKUP="$DIR/k_results_preinsert_20261021_193138.dump"
MARK="$DIR/.k_results_192_bg_20261021_started"
[[ "$(id -u)" == 0 ]] || { echo "STOP: root required for backup gate"; exit 1; }

state() {
  local day="$1" first last
  first="$(date -d "$day" +%Y%m%d)_"
  last="$(date -d "$day + 1 day" +%Y%m%d)_"
  runuser -u postgres -- psql -X -At -v ON_ERROR_STOP=1 -d railway -c "
  BEGIN READ ONLY;
  SELECT
    (SELECT count(*) FROM public.v2_races WHERE race_id >= '$first' AND race_id < '$last')::text || ':' ||
    (SELECT count(*) FROM public.v2_race_entries WHERE race_id >= '$first' AND race_id < '$last')::text || ':' ||
    (SELECT count(*) FROM public.v2_results WHERE race_id >= '$first' AND race_id < '$last')::text;
  COMMIT;" | grep -E '^[0-9]+:[0-9]+:[0-9]+$'
}

initial_gate() {
  local spec day expected actual
  for spec in \
    2026-10-08:144:864:97 \
    2026-10-15:156:936:32 \
    2026-10-16:156:936:135 \
    2026-10-17:168:1008:167; do
    day="$(cut -c1-10 <<< "$spec")"
    expected="$(cut -c12- <<< "$spec")"
    actual="$(state "$day")"
    echo "BASE_STATE $day $actual EXPECTED=$expected"
    [[ "$actual" == "$expected" ]] || {
      echo "STOP: historical DB changed before batch"; exit 1;
    }
  done
  echo "ALL_FOUR_BASE_STATES_MATCH"
}

old_backup_gate() {
  [[ -s "$OLD_BACKUP" && -s "$OLD_BACKUP.sha256" ]] || {
    echo "STOP: known older backup missing"; exit 1;
  }
  sha256sum -c "$OLD_BACKUP.sha256"
  local toc t
  toc="$(pg_restore --list "$OLD_BACKUP")"
  for t in v2_races v2_race_entries v2_results v2_result_entries; do
    grep -Eq "TABLE DATA public $t " <<< "$toc" || {
      echo "STOP: prior backup missing $t"; exit 1;
    }
  done
  echo "PRIOR_BACKUP_SHA_TOC_OK"
}

run_day() {
  local day="$1" races="$2" entries="$3" before="$4" add="$5"
  local remaining="$add" amount after actual
  while (( remaining > 0 )); do
    amount=$(( remaining > 24 ? 24 : remaining ))
    actual="$(state "$day")"
    echo "DAY_BATCH_BEFORE=$day:$actual EXPECTED=$races:$entries:$before"
    [[ "$actual" == "$races:$entries:$before" ]] || {
      echo "STOP: DB changed since previous verified batch"; exit 1;
    }
    nice -n 10 runuser -u postgres -- env \
      CONFIRM_V5_RESULTS_INSERT=YES HTTP_TIMEOUT=20 HTTP_MAX_RETRIES=0 \
      /opt/boat-ai-v5-venv/bin/python \
      deploy/conoha/k_missing_results_bounded_20261021.py \
      --day "$day" --expected-results "$before" --limit "$amount" --apply
    after=$((before + amount))
    actual="$(state "$day")"
    echo "DAY_BATCH_AFTER=$day:$actual EXPECTED=$races:$entries:$after"
    [[ "$actual" == "$races:$entries:$after" ]] || {
      echo "STOP: post-batch verification mismatch; do NOT rerun"; exit 1;
    }
    before="$after"
    remaining=$((remaining - amount))
    echo "BG_DAY_PROGRESS day=$day stored_results=$before remaining_standard=$remaining"
  done
}

if [[ "$*" == worker ]]; then
  echo "WORKER_STARTED $(date -Is)"
  old_backup_gate
  initial_gate
  echo "=== FRESH BACKUP OF 4 TABLES BEFORE ALL WRITES ==="
  bash deploy/conoha/backup_k_results_before_insert_20261021.sh
  initial_gate
  echo "=== INSERT-ONLY VERIFIED STANDARD RESULTS ==="
  run_day 2026-10-08 144 864 97 46
  run_day 2026-10-15 156 936 32 124
  run_day 2026-10-16 156 936 135 21
  run_day 2026-10-17 168 1008 167 1
  for spec in \
    2026-10-08:144:864:143 \
    2026-10-15:156:936:156 \
    2026-10-16:156:936:156 \
    2026-10-17:168:1008:168; do
    day="$(cut -c1-10 <<< "$spec")"
    expected="$(cut -c12- <<< "$spec")"
    actual="$(state "$day")"
    echo "FINAL_STATE $day $actual EXPECTED=$expected"
    [[ "$actual" == "$expected" ]] || {
      echo "STOP: final count mismatch; do NOT rerun"; exit 1;
    }
  done
  echo "ALL_192_STANDARD_RESULTS_COMPLETE"
  echo "ONLY_NONSTANDARD_REMAINING=20261008_14_05"
  echo "HISTORICAL_RETRIEVAL_NOT_PREDECISION"
  exit 0
fi

[[ "$*" == start || "$*" == "" ]] || { echo "STOP: expected start or worker"; exit 1; }
command -v systemd-run >/dev/null || { echo "STOP: systemd-run unavailable"; exit 1; }
bash -n "$SELF"
bash -n deploy/conoha/backup_k_results_before_insert_20261021.sh
/opt/boat-ai-v5-venv/bin/python -c 'import ast,pathlib; ast.parse(pathlib.Path("deploy/conoha/k_missing_results_bounded_20261021.py").read_text())'
if systemctl is-active --quiet boat-v5-kresults-72-20261021.service; then
  echo "STOP: preceding 72-result job is still running"; exit 1
fi
old_backup_gate
initial_gate
[[ ! -e "$MARK" ]] || { echo "STOP: this one-shot job already started; inspect logs"; exit 1; }
( set -C; printf '%s\n' "requested_at=$(date -Is)" > "$MARK" ) || {
  echo "STOP: could not create one-shot marker"; exit 1;
}
if ! systemd-run --unit="$UNIT" --collect --no-block \
  --property=Nice=10 --property=CPUQuota=50% \
  --property=MemoryMax=850M --property=RuntimeMaxSec=21600 \
  --property=Restart=no /bin/bash "$SELF" worker; then
  echo "STOP: service launch failed, marker kept to prevent rerun"; exit 1;
fi
echo "BG192_LAUNCHED_UNIT=$UNIT"
echo "STATUS: journalctl -u $UNIT -n 25 --no-pager"
echo "Launch does not mean the DB updates have completed."
