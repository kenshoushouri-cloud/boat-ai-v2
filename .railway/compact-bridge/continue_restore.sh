#!/usr/bin/env bash
set -euo pipefail

: "${SOURCE_DATABASE_URL:?SOURCE_DATABASE_URL required}"
: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL required}"

SRC_OPTS="-c default_transaction_read_only=on -c statement_timeout=0 -c work_mem=8MB -c max_parallel_workers_per_gather=0"
BIN_FILE="/tmp/race_entries_compact.bin"
POST_DATA="/tmp/post_data.sql"
POST_DATA_FILTERED="/tmp/post_data_filtered.sql"
CRITICAL_INDEX="ux_v2_odds_trifecta_race_ticket"

echo COMPACT_FULL_PREFLIGHT
unexpected="$(psql "$TARGET_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select count(*) from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind in ('r','p','v','m','S','f') and c.relname <> 'pg_health_check';")"
echo "COMPACT_TARGET_UNEXPECTED_PUBLIC_OBJECTS=$unexpected"
test "$unexpected" = "0"

echo COMPACT_FULL_PRE_DATA
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "drop table if exists public.pg_health_check cascade;"
PGOPTIONS="$SRC_OPTS" pg_dump "$SOURCE_DATABASE_URL" \
  --schema-only --section=pre-data --no-owner --no-acl \
  | psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1

echo COMPACT_FULL_CRITICAL_INDEX_EARLY
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c \
  "CREATE UNIQUE INDEX $CRITICAL_INDEX ON public.v2_odds_trifecta USING btree (race_id, ticket);"

echo COMPACT_FULL_OTHER_DATA
PGOPTIONS="$SRC_OPTS" pg_dump "$SOURCE_DATABASE_URL" \
  --data-only --no-owner --no-acl \
  --exclude-table-data=public.v2_race_entries \
  | psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1

echo COMPACT_FULL_RACE_EXPORT
cat > /tmp/export_race_entries.sql <<'SQL'
\copy (select (jsonb_populate_record(NULL::public.v2_race_entries,to_jsonb(e)-'recent_form')).* from public.v2_race_entries e order by race_id,lane) to '/tmp/race_entries_compact.bin' with (format binary)
SQL
PGOPTIONS="$SRC_OPTS" psql "$SOURCE_DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/export_race_entries.sql
test -s "$BIN_FILE"
stat -c 'COMPACT_BINARY_BYTES=%s' "$BIN_FILE"

echo COMPACT_FULL_RACE_IMPORT
cat > /tmp/import_race_entries.sql <<'SQL'
\copy public.v2_race_entries from '/tmp/race_entries_compact.bin' with (format binary)
SQL
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/import_race_entries.sql
rm -f "$BIN_FILE"

echo COMPACT_FULL_POST_DATA_PREPARE
PGOPTIONS="$SRC_OPTS" pg_dump "$SOURCE_DATABASE_URL" \
  --schema-only --section=post-data --no-owner --no-acl \
  > "$POST_DATA"

critical_count="$(grep -c "^CREATE UNIQUE INDEX $CRITICAL_INDEX " "$POST_DATA" || true)"
echo "COMPACT_CRITICAL_INDEX_DUMP_COUNT=$critical_count"
test "$critical_count" = "1"

grep -v "^CREATE UNIQUE INDEX $CRITICAL_INDEX " "$POST_DATA" > "$POST_DATA_FILTERED"
test "$(grep -c "^CREATE UNIQUE INDEX $CRITICAL_INDEX " "$POST_DATA_FILTERED" || true)" = "0"

echo COMPACT_FULL_POST_DATA
{
  echo "SET maintenance_work_mem='64MB';"
  echo "SET max_parallel_maintenance_workers=0;"
  cat "$POST_DATA_FILTERED"
} | psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1

rm -f "$POST_DATA" "$POST_DATA_FILTERED"
echo COMPACT_FULL_COMPLETED
