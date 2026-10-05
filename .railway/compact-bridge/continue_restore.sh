#!/usr/bin/env bash
set -euo pipefail

: "${SOURCE_DATABASE_URL:?SOURCE_DATABASE_URL required}"
: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL required}"

SRC_OPTS="-c default_transaction_read_only=on -c statement_timeout=0 -c work_mem=8MB -c max_parallel_workers_per_gather=0"

echo COMPACT_CONTINUE_CHECK_EMPTY
target_rows="$(psql "$TARGET_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select count(*) from public.v2_race_entries;")"
test "$target_rows" = "0"

echo COMPACT_CONTINUE_RACE_ENTRIES
cat >/tmp/export_race_entries.sql <<'SQL'
\copy (select (jsonb_populate_record(NULL::public.v2_race_entries,to_jsonb(e)-'recent_form')).* from public.v2_race_entries e order by race_id,lane) to stdout with (format binary)
SQL
cat >/tmp/import_race_entries.sql <<'SQL'
\copy public.v2_race_entries from stdin with (format binary)
SQL

PGOPTIONS="$SRC_OPTS" psql "$SOURCE_DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/export_race_entries.sql \
  | psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/import_race_entries.sql

echo COMPACT_CONTINUE_POST_DATA
{
  echo "SET maintenance_work_mem='64MB';"
  echo "SET max_parallel_maintenance_workers=0;"
  PGOPTIONS="$SRC_OPTS" pg_dump "$SOURCE_DATABASE_URL" \
    --schema-only --section=post-data --no-owner --no-acl
} | psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1

echo COMPACT_CONTINUE_COMPLETED
