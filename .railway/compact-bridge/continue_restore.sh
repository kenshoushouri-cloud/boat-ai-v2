#!/usr/bin/env bash
set -euo pipefail

: "${SOURCE_DATABASE_URL:?SOURCE_DATABASE_URL required}"
: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL required}"

SRC_OPTS="-c default_transaction_read_only=on -c statement_timeout=0 -c work_mem=8MB -c max_parallel_workers_per_gather=0"
BIN_FILE="/tmp/race_entries_compact.bin"

echo COMPACT_LOWWAL_PREFLIGHT
unexpected="$(psql "$TARGET_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select count(*) from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind in ('r','p','v','m','S','f') and c.relname <> 'pg_health_check';")"
echo "COMPACT_TARGET_UNEXPECTED_PUBLIC_OBJECTS=$unexpected"
test "$unexpected" = "0"

echo COMPACT_LOWWAL_TUNE
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "ALTER SYSTEM SET max_wal_size = '128MB';"
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "ALTER SYSTEM SET min_wal_size = '64MB';"
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "ALTER SYSTEM SET wal_compression = 'on';"
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT pg_reload_conf();"
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "CHECKPOINT;"

echo COMPACT_LOWWAL_PRE_DATA
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "drop table if exists public.pg_health_check cascade;"
PGOPTIONS="$SRC_OPTS" pg_dump "$SOURCE_DATABASE_URL" \
  --schema-only --section=pre-data --no-owner --no-acl \
  | psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1

echo COMPACT_LOWWAL_OTHER_DATA
PGOPTIONS="$SRC_OPTS" pg_dump "$SOURCE_DATABASE_URL" \
  --data-only --no-owner --no-acl \
  --exclude-table-data=public.v2_race_entries \
  | psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1

echo COMPACT_LOWWAL_RACE_EXPORT
cat > /tmp/export_race_entries.sql <<'SQL'
\copy (select (jsonb_populate_record(NULL::public.v2_race_entries,to_jsonb(e)-'recent_form')).* from public.v2_race_entries e order by race_id,lane) to '/tmp/race_entries_compact.bin' with (format binary)
SQL
PGOPTIONS="$SRC_OPTS" psql "$SOURCE_DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/export_race_entries.sql
test -s "$BIN_FILE"
stat -c 'COMPACT_BINARY_BYTES=%s' "$BIN_FILE"

echo COMPACT_LOWWAL_RACE_IMPORT
cat > /tmp/import_race_entries.sql <<'SQL'
\copy public.v2_race_entries from '/tmp/race_entries_compact.bin' with (format binary)
SQL
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/import_race_entries.sql
rm -f "$BIN_FILE"

echo COMPACT_LOWWAL_CHECKPOINT_BEFORE_INDEXES
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "CHECKPOINT;"

echo COMPACT_LOWWAL_POST_DATA
{
  echo "SET maintenance_work_mem='64MB';"
  echo "SET max_parallel_maintenance_workers=0;"
  PGOPTIONS="$SRC_OPTS" pg_dump "$SOURCE_DATABASE_URL" \
    --schema-only --section=post-data --no-owner --no-acl
} | psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1

echo COMPACT_LOWWAL_CHECKPOINT_AFTER_INDEXES
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "CHECKPOINT;"

echo COMPACT_LOWWAL_RESET
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "ALTER SYSTEM RESET max_wal_size;"
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "ALTER SYSTEM RESET min_wal_size;"
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "ALTER SYSTEM RESET wal_compression;"
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT pg_reload_conf();"
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "CHECKPOINT;"

echo COMPACT_LOWWAL_COMPLETED
