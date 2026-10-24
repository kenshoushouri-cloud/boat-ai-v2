#!/usr/bin/env bash
# One-command V5 migration PREPARATION. No production DB writes or service changes.
# Generates reusable inventory, grouped batch plan, backup metadata and gate report.
# FAIL CLOSED: this is NOT a cutover script or its timer.
set -euo pipefail
umask 077
export LC_ALL=C
ROOT=/opt/boat-ai-v5
OUTROOT=/var/backups
test "$(id -u)" -eq 0 || { echo 'NO_GO_NOT_ROOT'; exit 2; }
test -d "$ROOT/.git" || { echo 'NO_GO_GIT_REPOSITORY_MISSING'; exit 2; }
test -d "$OUTROOT" || { echo 'NO_GO_BACKUP_DIRECTORY_MISSING'; exit 2; }
OUT=$(mktemp -d "$OUTROOT/v5_prepare_XXXXXXXX")
TEMP=$(mktemp -d /tmp/v5_prepare_code_XXXXXXXX)
trap 'rm -rf -- "$TEMP"' EXIT

echo "=== V5 ONE COMMAND PREPARE ==="
echo "REPORT_DIR=$OUT"

# All read-only inputs come from the same fetched GitHub commit.
for pair in \
  "deploy/conoha/v5_stage_13_batch_gate_readonly_20261024.sql:source_gate.sql" \
  "deploy/conoha/v5_cutover_writer_inventory_readonly_20261024.sh:writer_audit.sh" \
  "docs/BOAT_SHARED_13_SOURCE_ROUTE_MANIFEST_20261023.json:source_map.json"
do
  source_path=$(printf '%s' "$pair" | cut -d: -f1)
  output_name=$(printf '%s' "$pair" | cut -d: -f2)
  timeout -k 2s 12s git -C "$ROOT" show "FETCH_HEAD:$source_path" \
    > "$TEMP/$output_name" || { echo "NO_GO_SOURCE_FETCH=$source_path"; exit 2; }
done

python3 - "$TEMP/source_map.json" "$OUT/01_canonical_source_map.txt" <<'PY'
import json,sys
j=json.load(open(sys.argv[1],encoding='utf-8'))
rows=j.get('tables')
if not isinstance(rows,list) or len(rows)!=13: raise SystemExit('NO_GO_13_MANIFEST_INVALID')
sources=[r.get('legacy_relation') for r in rows]
targets=[r.get('canonical_relation') for r in rows]
if len(set(sources))!=13 or len(set(targets))!=13: raise SystemExit('NO_GO_DUPLICATE_SOURCE_OR_TARGET')
if any(not isinstance(s,str) or not s.startswith('public.v2_') for s in sources):
    raise SystemExit('NO_GO_UNKNOWN_SOURCE_NAME')
if any(not isinstance(s,str) or not s.startswith('boat_data.') for s in targets):
    raise SystemExit('NO_GO_UNKNOWN_CANONICAL_NAME')
with open(sys.argv[2],'w',encoding='utf-8') as f:
    f.write('V5 13-SOURCE CANONICAL MAP / source table -> shared VIEW\n')
    for row in rows:
        f.write(row['legacy_relation']+' -> '+row['canonical_relation']+'\n')
    f.write('\nDo not recopy existing boat_data_stage.venues 24 rows.\n')
print('FIXED_SOURCE_MANIFEST=13_UNIQUE_PASS')
PY

echo "=== DB SOURCE/CANDIDATE READ ONLY ==="
timeout -k 2s 45s runuser -u postgres -- \
 psql -X -P pager=off -v ON_ERROR_STOP=1 -d railway \
 -f "$TEMP/source_gate.sql" > "$OUT/02_db_gate.txt"
grep -q 'V5_13_SOURCE_BATCH_GATE_READONLY_DONE_NO_COPY' "$OUT/02_db_gate.txt" || {
  echo 'NO_GO_DB_GATE_INCOMPLETE'
  exit 2
}
echo 'DB_GATE_READ_ONLY_PASS'

echo "=== SYSTEMD/CRON/PG WRITERS READ ONLY ==="
timeout -k 2s 45s bash "$TEMP/writer_audit.sh" > "$OUT/03_writer_audit.txt"
grep -q 'V5_WRITER_INVENTORY_READ_ONLY_FINISHED' "$OUT/03_writer_audit.txt" || {
  echo 'NO_GO_WRITER_AUDIT_INCOMPLETE'
  exit 2
}
echo 'WRITER_INVENTORY_READ_ONLY_PASS'

echo "=== LOCAL BACKUP/DISK FILES (NO RESTORE) ==="
{
  printf 'JST %s\n' "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')"
  df -h "$OUTROOT"
  echo 'LOCAL_BACKUP_CANDIDATES:'
  find "$OUTROOT" -maxdepth 1 -type f \
    \( -name '*railway*' -o -name '*archive*' -o -name '*boat-ai*' \) \
    -printf '%f | %s bytes | %TY-%Tm-%Td\n' | head -35 || true
  echo 'Local backups are NOT independent off-VPS restoration proof.'
} > "$OUT/04_backup_disk_inventory.txt"

echo "=== STAGE BATCH AND UNATTENDED WINDOW PLAN ==="
cat > "$OUT/05_stage_and_night_plan.txt" <<'PLAN'
CURRENT_STATE: live 13 boat_data VIEWs, one isolated venues stage already copied.
DAYTIME_WAVE_1: races, entries, official results, K results, exhibition, odds
DAYTIME_WAVE_2: course stats, entry/odds snapshots, weather, race/racer conditions
METHOD: verify PK/UNIQUE/NULL/default/sequence/FK/index/trigger/ACL per source,
        create separately approved physical stages, low-load chunked online copy
        while legacy collectors keep writing, then INSERT/UPDATE/DELETE catchup.
        Preserve all source metadata; never recopy venues pilot.
UNATTENDED_CANDIDATE: future 03:30-04:00 JST only. No job armed here.
PRE_WINDOW: independently verified offsite backup restoration, certified writers,
            completed 01:20 catchup + no pending result/K, tested rollback,
            sufficient disk/WAL, next 07:00 collection preserved.
CUTOVER: all gates true -> pause affected writers/children/timers, final parity,
         approved atomic route switch, nonbuy canary, restart collectors.
ON_ANY_ERROR: abort or proven automatic route rollback + collector restart.
BACKFILL: official results and K may be recovered later; exhibition/odds/weather
          retrieved later are RETROSPECTIVE and NEVER first-capture proof.
NO BUY, NO source deletion, NO old V3/V4 backup overwrite.
PLAN

cat > "$OUT/06_cutover_gate.txt" <<'GATES'
PRODUCTION_CUTOVER=NO_GO
AUTOMATIC_NIGHT_SWITCH=NOT_INSTALLED_NOT_ARMED
NEW_PHYSICAL_STAGE_COPY=NOT_EXECUTED
INDEPENDENT_OFFHOST_BACKUP_RESTORE=UNVERIFIED
ALL_RUNTIME_WRITERS=UNCERTIFIED
BATCH_UPSERT_DELETE_CATCHUP=NOT_TESTED
AUTOMATIC_ROLLBACK_AND_SERVICE_RESTART=NOT_TESTED
FINAL_CUTOVER_SCOPE_APPROVAL=NOT_YET_VALIDATED
NEXT=Implement/test approved chunked stage copier and automatic recovery gate.
GATES

printf 'PREPARATION_REPORT=%s\n' "$OUT"
echo 'SOURCE_SYSTEM_UNCHANGED=YES'
echo 'V5_PREPARE_ONE_COMMAND_COMPLETE'
echo 'PRODUCTION_CUTOVER=NO_GO'
echo 'NIGHT_AUTOMATION=NOT_ARMED'
