#!/usr/bin/env bash
# V5 stage-copy preflight: independent recovery evidence gap + live headroom.
# READ ONLY: never uploads, backs up, copies or changes DB.
# TOC and same-VPS SHA checks do NOT prove off-host restorability/freshness.
set -euo pipefail
export LC_ALL=C
umask 077

railway=/var/backups/boat-railway-20261023-ORfLpY/railway.dump
archive=/var/backups/boat-history-20261024-U6CRLt/boat_history_archive.dump
railway_size=393138215
archive_size=81865791
railway_sha=4ee6a5d9c1ddf67c61b8bb82426961431c25f20f944f87b6cef5137bb294478d
archive_sha=7301975821593cdab2fdcf30eedc8d78558537023ed7af30f03d679de19fd37e

# Older backup paths may differ; use exact filename+bytes+SHA under
# existing /var/backups only. No uploads, recreations or overwrites.
resolve_archive_location() {
  local file bytes digest
  local matches=0
  local chosen=''
  local examined=0
  while IFS= read -r -d '' file; do
    examined=$((examined+1))
    if [ "$examined" -gt 12 ]; then
      echo 'NO_GO_ARCHIVE_TOO_MANY_CANDIDATES' >&2
      return 2
    fi
    [ -r "$file" ] || continue
    bytes=$(stat -c %s -- "$file")
    [ "$bytes" = "$archive_size" ] || continue
    digest=$(timeout -k 2s 100s nice -n 15 sha256sum -- "$file" |
      awk '{print $1}')
    if [ "$digest" = "$archive_sha" ]; then
      chosen=$file
      matches=$((matches+1))
    fi
  done < <(timeout -k 2s 12s find /var/backups -maxdepth 3 \
      -type f -name boat_history_archive.dump -print0)
  if [ "$matches" -ne 1 ]; then
    echo "NO_GO_ARCHIVE_MATCHING_SHA_COUNT=$matches" >&2
    return 2
  fi
  archive=$chosen
  echo 'ARCHIVE_BACKUP_MATCHED_BY_SIZE_SHA=YES'
}

echo "=== V5 LOCAL BACKUP AND PHYSICAL STAGE CAPACITY PRECHECK ==="
echo "INSPECTED_AT_JST=$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S %Z')"

if [ ! -f "$archive" ] || [ ! -r "$archive" ]; then
  echo 'ARCHIVE_RECORDED_PATH_NOT_READABLE_SEARCHING_KNOWN_BACKUP_ROOT'
  resolve_archive_location
fi

for kind in railway archive; do
    case "$kind" in
      railway) file=$railway; expected_bytes=$railway_size; expected_sha=$railway_sha;;
      archive) file=$archive; expected_bytes=$archive_size; expected_sha=$archive_sha;;
    esac
    if [ ! -f "$file" ] || [ ! -r "$file" ]; then
      echo "NO_GO_LOCAL_DUMP_NOT_READABLE=$kind"; exit 2
    fi
    bytes=$(stat -c %s -- "$file")
    if [ "$bytes" != "$expected_bytes" ]; then
      echo "NO_GO_LOCAL_DUMP_SIZE_MISMATCH=$kind"; exit 2
    fi
    actual_sha=$(timeout -k 2s 100s nice -n 15 sha256sum -- "$file" | awk '{print $1}')
    if [ "$actual_sha" != "$expected_sha" ]; then
      echo "NO_GO_LOCAL_DUMP_SHA256_MISMATCH=$kind"; exit 2
    fi
    timeout -k 2s 30s nice -n 15 pg_restore -l "$file" >/dev/null || {
      echo "NO_GO_LOCAL_DUMP_TOC_FAILED=$kind"; exit 2;
    }
    echo "LOCAL_DUMP_KIND=$kind SIZE_SHA_TOC=PASS"
done

echo "=== PostgreSQL database sizes and WAL usage (CATALOG ONLY) ==="
timeout -k 2s 20s runuser -u postgres -- psql -X -P pager=off \
  -v ON_ERROR_STOP=1 -d railway <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='1s';
SELECT d.datname AS database,pg_size_pretty(pg_database_size(d.datname)) AS size
FROM pg_database d
WHERE d.datname IN ('railway','boat_history_archive')
ORDER BY d.datname;
SELECT count(*) AS wal_segments,
       pg_size_pretty(coalesce(sum(size),0)::bigint) AS wal_size
FROM pg_ls_waldir();
SELECT count(*) FILTER (WHERE to_regclass(name) IS NOT NULL) AS
  physical_stage_candidates_currently_present
FROM (VALUES ('boat_data_stage.races'),
 ('boat_data_stage.entries'),('boat_data_stage.results'),
 ('boat_data_stage.racer_results'),('boat_data_stage.trifecta_odds'),
 ('boat_data_stage.exhibition_snapshots'),
 ('boat_data_stage.racer_course_stats_snapshots'),
 ('boat_data_stage.entry_snapshots'),('boat_data_stage.odds_snapshots'),
 ('boat_data_stage.weather_snapshots'),
 ('boat_data_stage.race_condition_snapshots'),
 ('boat_data_stage.racer_condition_snapshots')) x(name);
ROLLBACK;
SQL

echo "=== DISK SPACE ON DATABASE AND BACKUP MOUNTS ==="
pgdir=$(timeout -k 2s 10s runuser -u postgres -- psql -X -At \
 -v ON_ERROR_STOP=1 -d railway -c "SHOW data_directory" | head -n 1)
if [ -z "$pgdir" ] || [ ! -d "$pgdir" ]; then
  echo "NO_GO_DB_STORAGE_PATH_UNKNOWN"; exit 2
fi
df -Pm -- "$pgdir" /var/backups |
  awk 'NR==1 {print; next} !seen[$1]++'

echo "LOCAL_BACKUP_INTEGRITY=PASS_SAME_VPS_ONLY"
echo "INDEPENDENT_OFFHOST_RESTORE=UNVERIFIED"
echo "V5_STAGE_PERSISTENT_DDL=NO_GO_UNTIL_RESTORE_AND_SCOPED_APPROVAL"
echo "NIGHT_AUTO_CUTOVER=NOT_ARMED"
echo "V5_STAGE_BACKUP_CAPACITY_READONLY_FINISHED"
