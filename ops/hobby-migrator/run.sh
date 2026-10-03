#!/usr/bin/env bash
set -euo pipefail

: "${SOURCE_DATABASE_URL:?SOURCE_DATABASE_URL is required}"
: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL is required}"

MIGRATION_MODE="${MIGRATION_MODE:-HOT_SEED}"

if [[ "$MIGRATION_MODE" == "ARCHIVE_RACE_CONDITION" ]]; then
  : "${ARCHIVE_CUTOFF:?ARCHIVE_CUTOFF is required}"
  : "${ARCHIVE_EXPECTED_ROWS:?ARCHIVE_EXPECTED_ROWS is required}"
  if [[ ! "$ARCHIVE_CUTOFF" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "ARCHIVE_COPY_ABORT=invalid_cutoff" >&2
    exit 11
  fi
  if [[ ! "$ARCHIVE_EXPECTED_ROWS" =~ ^[0-9]+$ ]] || [[ "$ARCHIVE_EXPECTED_ROWS" == "0" ]]; then
    echo "ARCHIVE_COPY_ABORT=invalid_expected_rows" >&2
    exit 12
  fi

  echo "ARCHIVE_COPY_SOURCE_WRITE=0 TARGET_ONLY_WRITE=1 CUTOFF=$ARCHIVE_CUTOFF"

  PGOPTIONS="-c default_transaction_read_only=on -c temp_file_limit=65536" \
  psql "$SOURCE_DATABASE_URL" -X -q -v ON_ERROR_STOP=1 \
    -v archive_url="$TARGET_DATABASE_URL" \
    -v cutoff="$ARCHIVE_CUTOFF" \
    -v expected="$ARCHIVE_EXPECTED_ROWS" <<'SQL'
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT dblink_connect('archive_copy', :'archive_url');
SELECT dblink_exec('archive_copy', 'BEGIN');

DO $archive_copy$
DECLARE
  cutoff_date date := :'cutoff'::date;
  expected_rows bigint := :'expected'::bigint;
  source_rows bigint;
  archive_rows bigint;
  batch_size integer := 250;
  offset_rows integer := 0;
  payload text;
  remote_sql text;
BEGIN
  SELECT count(*)::bigint INTO source_rows
  FROM public.v2_realtime_race_condition_snapshots s
  JOIN public.v2_races r ON r.race_id = s.race_id
  WHERE r.race_date < cutoff_date;

  IF source_rows <> expected_rows THEN
    RAISE EXCEPTION 'source_count_changed';
  END IF;

  SELECT n INTO archive_rows
  FROM dblink(
    'archive_copy',
    'SELECT count(*)::bigint FROM archive.v2_realtime_race_condition_snapshots'
  ) AS t(n bigint);

  IF archive_rows <> 0 THEN
    RAISE EXCEPTION 'archive_receiver_not_empty';
  END IF;

  LOOP
    SELECT coalesce(json_agg(x), '[]'::json)::text
      INTO payload
    FROM (
      SELECT s.*
      FROM public.v2_realtime_race_condition_snapshots s
      JOIN public.v2_races r ON r.race_id = s.race_id
      WHERE r.race_date < cutoff_date
      ORDER BY s.ctid
      LIMIT batch_size OFFSET offset_rows
    ) AS x;

    EXIT WHEN payload = '[]';

    remote_sql :=
      'INSERT INTO archive.v2_realtime_race_condition_snapshots ' ||
      'SELECT * FROM json_populate_recordset(' ||
      'NULL::archive.v2_realtime_race_condition_snapshots,' ||
      quote_literal(payload) || '::json)';

    PERFORM dblink_exec('archive_copy', remote_sql);
    offset_rows := offset_rows + batch_size;
  END LOOP;

  SELECT n INTO archive_rows
  FROM dblink(
    'archive_copy',
    'SELECT count(*)::bigint FROM archive.v2_realtime_race_condition_snapshots'
  ) AS t(n bigint);

  IF archive_rows <> expected_rows THEN
    RAISE EXCEPTION 'archive_post_count_mismatch';
  END IF;

  SELECT count(*)::bigint INTO source_rows
  FROM public.v2_realtime_race_condition_snapshots s
  JOIN public.v2_races r ON r.race_id = s.race_id
  WHERE r.race_date < cutoff_date;

  IF source_rows <> expected_rows THEN
    RAISE EXCEPTION 'source_snapshot_drift';
  END IF;

  RAISE NOTICE 'ARCHIVE_COPY_VERIFIED source=% archive=%', source_rows, archive_rows;
EXCEPTION WHEN OTHERS THEN
  BEGIN
    PERFORM dblink_exec('archive_copy', 'ROLLBACK');
  EXCEPTION WHEN OTHERS THEN
    NULL;
  END;
  RAISE;
END
$archive_copy$;

SELECT dblink_exec('archive_copy', 'COMMIT');
SELECT dblink_disconnect('archive_copy');
ROLLBACK;
SQL

  echo "ARCHIVE_COPY_RESULT=PASS"
  echo "ARCHIVE_COPY_ROWS=$ARCHIVE_EXPECTED_ROWS"
  echo "PRODUCTION_DELETE=0"
  echo "VACUUM_OR_REWRITE=0"
  exit 0
fi
: "${HOT_CUTOFF:?HOT_CUTOFF is required}"
if [[ ! "$HOT_CUTOFF" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "HOBBY_MIGRATION_ABORT=invalid_cutoff" >&2
  exit 10
fi

echo "HOBBY_MIGRATION_SOURCE_WRITE=0 TARGET_ONLY_WRITE=1 HOT_CUTOFF=$HOT_CUTOFF"

target_tables="$(psql "$TARGET_DATABASE_URL" -Atqc "select count(*) from pg_catalog.pg_tables where schemaname='public'")"
if [[ "$target_tables" != "0" ]]; then
  echo "HOBBY_MIGRATION_ABORT=target_not_empty table_count=$target_tables" >&2
  exit 20
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
