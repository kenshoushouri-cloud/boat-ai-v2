#!/usr/bin/env bash
# Safe local DB backup checkpoint before missing official K result INSERT pilot.
# Backs up the 4 existing tables only; does not change DB, services, or cron.
set -euo pipefail
umask 077

DIR=/root/boat-v5-backups
install -d -m 700 "$DIR"
if [[ "$(id -u)" != "0" ]]; then
  echo "STOP: run as root for private backup location"; exit 1
fi
AVAIL_KB="$(df -Pk "$DIR" | awk 'NR==2{print $4}')"
if [[ ! "$AVAIL_KB" =~ ^[0-9]+$ ]] || (( AVAIL_KB < 1048576 )); then
  echo "STOP: less than 1 GiB free on local backup volume"; exit 1
fi
OUT="$DIR/k_results_preinsert_$(date +%Y%m%d_%H%M%S).dump"
if [[ -e "$OUT" || -e "$OUT.sha256" ]]; then
  echo "STOP: backup filename collision"; exit 1
fi
TMP="$(mktemp "$DIR/.k_results_preinsert_XXXXXX.partial")"
trap 'rm -f "$TMP"' EXIT
echo "DISK_AVAILABLE_KB=$AVAIL_KB"
echo "BACKUP_START"
nice -n 10 runuser -u postgres -- pg_dump -Fc -d railway \
  -t public.v2_races \
  -t public.v2_race_entries \
  -t public.v2_results \
  -t public.v2_result_entries > "$TMP"
test -s "$TMP"
echo "VERIFY_BACKUP_TOC"
TOC="$(pg_restore --list "$TMP")"
for TABLE in v2_races v2_race_entries v2_results v2_result_entries; do
  if ! printf '%s\n' "$TOC" | grep -Eq "TABLE DATA public ${TABLE} "; then
    echo "STOP: missing TABLE DATA for $TABLE"; exit 1
  fi
  echo "TABLE_DATA_OK=$TABLE"
done
mv -n "$TMP" "$OUT"
if [[ ! -s "$OUT" ]]; then
  echo "STOP: backup move failed"; exit 1
fi
trap - EXIT
sha256sum "$OUT" > "$OUT.sha256"
sha256sum -c "$OUT.sha256"
ls -lh "$OUT"
echo "FOUR_TABLE_FRESH_BACKUP_OK=$OUT"
echo "LOCAL_BACKUP_ONLY_NO_DB_WRITES"
