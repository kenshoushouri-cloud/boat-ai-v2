#!/usr/bin/env bash
# V5 migration writer inventory. SAFE: read-only, no service changes.
# Does NOT certify all runtime writers or authorize cutover.
set -euo pipefail
export LC_ALL=C
echo '=== V5 WRITER INVENTORY READ ONLY ==='
echo "NOW_JST=$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S %Z')"
for name in boat-v5-daily@morning boat-v5-daily@night boat-v5-forward-window boat-v5-midnight-catchup; do
  timer_active=$(systemctl show "$name.timer" --property=ActiveState --value --no-pager 2>/dev/null || true)
  timer_enabled=$(systemctl show "$name.timer" --property=UnitFileState --value --no-pager 2>/dev/null || true)
  next=$(systemctl show "$name.timer" --property=NextElapseUSecRealtime --value --no-pager 2>/dev/null || true)
  service_active=$(systemctl show "$name.service" --property=ActiveState --value --no-pager 2>/dev/null || true)
  mainpid=$(systemctl show "$name.service" --property=MainPID --value --no-pager 2>/dev/null || true)
  printf 'UNIT|%s|timer=%s|enabled=%s|service=%s|pid=%s|next=%s\n' "$name" "$timer_active" "$timer_enabled" "$service_active" "$mainpid" "$next"
done

echo '=== OTHER BOAT/V5 UNITS (NAMES ONLY) ==='
timeout -k 2s 10s systemctl list-units --all --plain --no-legend --no-pager 2>/dev/null \
  | awk '$1 ~ /boat|v5/ && $1 ~ /\.service$/ {print $1"|"$3}' \
  | head -30 || true

echo '=== COLLECTOR PROCESS NAMES ONLY (NO ARGUMENTS) ==='
ps -eo pid=,ppid=,comm= \
 | awk '$3 ~ /^(python|python3|python3[.][0-9]+|rclone|pg_dump|psql|bash|sh)$/ {print $1"|"$2"|"$3; if (++n>=35) exit}'
echo '=== CRON MATCH COUNTS (NO COMMANDS) ==='
for who in root postgres; do
  rows=$(timeout -k 2s 6s crontab -u "$who" -l 2>/dev/null || true)
  count=$(printf '%s\n' "$rows" | awk 'NF && $0 !~ /^[[:space:]]*#/ && tolower($0) ~ /boat|v5/ {n++} END {print n+0}')
  printf 'CRON|%s|boat_v5_entries=%s\n' "$who" "$count"
done
echo '=== POSTGRES DATABASE SESSION STATES ONLY ==='
timeout -k 2s 12s runuser -u postgres -- \
  psql -X -P pager=off -v ON_ERROR_STOP=1 -d railway <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='5s';
SET LOCAL lock_timeout='1s';
SELECT coalesce(state,'unknown') AS session_state,
       coalesce(wait_event_type,'-') AS wait_type,
       count(*) AS connections
FROM pg_stat_activity
WHERE datname='railway' AND pid<>pg_backend_pid()
GROUP BY state,wait_event_type
ORDER BY 1,2;
ROLLBACK;
SQL
echo 'V5_WRITER_INVENTORY_READ_ONLY_FINISHED'
