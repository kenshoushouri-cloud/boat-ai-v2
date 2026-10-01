#!/usr/bin/env bash
# branch-deploy-trigger-v2
set -euo pipefail

: "${SOURCE_DATABASE_URL:?SOURCE_DATABASE_URL is required}"
: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL is required}"
: "${HOT_CUTOFF:?HOT_CUTOFF is required}"
if [[ ! "$HOT_CUTOFF" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "HOBBY_MIGRATION_ABORT=invalid_cutoff" >&2
  exit 10
fi

echo "HOBBY_MIGRATION_SOURCE_WRITE=0 TARGET_ONLY_WRITE=1 HOT_CUTOFF=$HOT_CUTOFF"

target_tables="$(psql "$TARGET_DATABASE_URL" -Atqc "select count(*) from pg_catalog.pg_tables where schemaname='public'")"
if [[ "$target_tables" != "0" ]]; then
  echo "HOBBY_MIGRATION_MODE=READ_ONLY_AUDIT_EXISTING_TARGET table_count=$target_tables"
  export PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=120000"

  fail=0
  src_size="$(psql "$SOURCE_DATABASE_URL" -Atqc "select pg_database_size(current_database())")"
  tgt_size="$(psql "$TARGET_DATABASE_URL" -Atqc "select pg_database_size(current_database())")"
  echo "HOBBY_AUDIT_SOURCE_DB_BYTES=$src_size"
  echo "HOBBY_AUDIT_TARGET_DB_BYTES=$tgt_size"

  for t in v2_races v2_race_entries v2_results v2_result_entries; do
    src_n="$(psql "$SOURCE_DATABASE_URL" -Atqc "select count(*) from public.$t")"
    tgt_n="$(psql "$TARGET_DATABASE_URL" -Atqc "select count(*) from public.$t")"
    echo "HOBBY_AUDIT_BASE table=$t source=$src_n target=$tgt_n"
    if [[ "$src_n" != "$tgt_n" ]]; then
      fail=1
    fi
  done

  hot_tables=(
    v2_odds_trifecta
    v2_realtime_racer_condition_snapshots
    v2_realtime_weather_snapshots
    v2_realtime_race_condition_snapshots
    v2_realtime_exhibition_snapshots
  )

  for t in "${hot_tables[@]}"; do
    src_hot="$(psql "$SOURCE_DATABASE_URL" -Atqc "select count(*) from public.$t x join public.v2_races r on r.race_id=x.race_id where r.race_date >= date '$HOT_CUTOFF'")"
    tgt_total="$(psql "$TARGET_DATABASE_URL" -Atqc "select count(*) from public.$t")"
    tgt_old="$(psql "$TARGET_DATABASE_URL" -Atqc "select count(*) from public.$t x join public.v2_races r on r.race_id=x.race_id where r.race_date < date '$HOT_CUTOFF'")"
    echo "HOBBY_AUDIT_HOT table=$t source_hot=$src_hot target_total=$tgt_total target_old=$tgt_old"
    if [[ "$src_hot" != "$tgt_total" || "$tgt_old" != "0" ]]; then
      fail=1
    fi
  done

  for t in v2_realtime_odds_snapshots v2_v24_motor2_forward_shadow v2_racer_course_stats_snapshots v2_realtime_entry_snapshots v2_opponent_pressure_shadow_v2; do
    src_n="$(psql "$SOURCE_DATABASE_URL" -Atqc "select count(*) from public.$t")"
    tgt_n="$(psql "$TARGET_DATABASE_URL" -Atqc "select count(*) from public.$t")"
    echo "HOBBY_AUDIT_OBSERVE table=$t source=$src_n target=$tgt_n"
  done

  if [[ "$fail" != "0" ]]; then
    echo "HOBBY_MIGRATION_RESULT=FAIL_EXISTING_TARGET_PARITY" >&2
    exit 0
  fi

  echo "HOBBY_MIGRATION_RESULT=PASS_EXISTING_TARGET_PARITY"
  exit 0
fi

dump=/tmp/hobby-migration.dump
rm -f "$dump"

echo "HOBBY_MIGRATION_STAGE=dump_filtered_seed"
pg_dump "$SOURCE_DATABASE_URL" --format=custom --no-owner --no-acl \
  --exclude-table-data=public.v2_odds_trifecta \
  --exclude-table-data=public.v2_realtime_racer_condition_snapshots \
  --exclude-table-data=public.v2_realtime_weather_snapshots \
  --exclude-table-data=public.v2_realtime_race_condition_snapshots \
  --exclude-table-data=public.v2_realtime_exhibition_snapshots \
  --file="$dump"
echo "HOBBY_MIGRATION_DUMP_BYTES=$(stat -c %s "$dump")"

echo "HOBBY_MIGRATION_STAGE=restore_filtered_seed"
pg_restore --clean --if-exists --no-owner --no-acl --exit-on-error \
  --dbname="$TARGET_DATABASE_URL" "$dump"

tables=(
  v2_odds_trifecta
  v2_realtime_racer_condition_snapshots
  v2_realtime_weather_snapshots
  v2_realtime_race_condition_snapshots
  v2_realtime_exhibition_snapshots
)

for t in "${tables[@]}"; do
  src_n="$(psql "$SOURCE_DATABASE_URL" -Atqc "select count(*) from public.$t x where exists (select 1 from public.v2_races r where r.race_id=x.race_id and r.race_date >= date '$HOT_CUTOFF')")"
  echo "HOBBY_MIGRATION_HOT_SOURCE table=$t rows=$src_n"
  psql "$SOURCE_DATABASE_URL" -qAt -v ON_ERROR_STOP=1 \
    -c "\copy (select x.* from public.$t x where exists (select 1 from public.v2_races r where r.race_id=x.race_id and r.race_date >= date '$HOT_CUTOFF')) TO STDOUT WITH (FORMAT csv)" \
    | psql "$TARGET_DATABASE_URL" -q -v ON_ERROR_STOP=1 \
      -c "\copy public.$t FROM STDIN WITH (FORMAT csv)"
  tgt_n="$(psql "$TARGET_DATABASE_URL" -Atqc "select count(*) from public.$t")"
  echo "HOBBY_MIGRATION_HOT_TARGET table=$t rows=$tgt_n"
  if [[ "$src_n" != "$tgt_n" ]]; then
    echo "HOBBY_MIGRATION_ABORT=hot_parity table=$t source=$src_n target=$tgt_n" >&2
    exit 30
  fi
done

for t in v2_races v2_race_entries v2_results v2_result_entries; do
  src_n="$(psql "$SOURCE_DATABASE_URL" -Atqc "select count(*) from public.$t")"
  tgt_n="$(psql "$TARGET_DATABASE_URL" -Atqc "select count(*) from public.$t")"
  echo "HOBBY_MIGRATION_BASE_PARITY table=$t source=$src_n target=$tgt_n"
  if [[ "$src_n" != "$tgt_n" ]]; then
    echo "HOBBY_MIGRATION_ABORT=base_parity table=$t source=$src_n target=$tgt_n" >&2
    exit 40
  fi
done

psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -q -c "ANALYZE"
size="$(psql "$TARGET_DATABASE_URL" -Atqc "select pg_database_size(current_database())")"
echo "HOBBY_MIGRATION_TARGET_DB_BYTES=$size"
rm -f "$dump"
echo "HOBBY_MIGRATION_RESULT=PASS_INITIAL_SEED"
