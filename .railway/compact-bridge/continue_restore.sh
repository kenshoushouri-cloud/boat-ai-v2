#!/usr/bin/env bash
set -euo pipefail

: "${SOURCE_DATABASE_URL:?SOURCE_DATABASE_URL required}"
: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL required}"

SRC_OPTS="-c default_transaction_read_only=on -c statement_timeout=0 -c work_mem=8MB -c max_parallel_workers_per_gather=0"
TGT_OPTS="-c default_transaction_read_only=on -c statement_timeout=0 -c work_mem=8MB -c max_parallel_workers_per_gather=0"
SRC_BIN="/tmp/source_compact.bin"
TGT_BIN="/tmp/target_compact.bin"

echo PARITY_CHECK_META
source_rows="$(PGOPTIONS="$SRC_OPTS" psql "$SOURCE_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select count(*) from public.v2_race_entries;")"
target_rows="$(PGOPTIONS="$TGT_OPTS" psql "$TARGET_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select count(*) from public.v2_race_entries;")"
target_recent="$(PGOPTIONS="$TGT_OPTS" psql "$TARGET_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select count(*) from public.v2_race_entries where recent_form is not null;")"
source_db_bytes="$(PGOPTIONS="$SRC_OPTS" psql "$SOURCE_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select pg_database_size(current_database());")"
target_db_bytes="$(PGOPTIONS="$TGT_OPTS" psql "$TARGET_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select pg_database_size(current_database());")"

echo "PARITY_SOURCE_ROWS=$source_rows"
echo "PARITY_TARGET_ROWS=$target_rows"
echo "PARITY_TARGET_RECENT_FORM_NONEMPTY=$target_recent"
echo "PARITY_SOURCE_DB_BYTES=$source_db_bytes"
echo "PARITY_TARGET_DB_BYTES=$target_db_bytes"

test "$source_rows" = "$target_rows"
test "$target_recent" = "0"

echo PARITY_EXPORT_SOURCE
cat >/tmp/export_source.sql <<'SQL'
\copy (select (jsonb_populate_record(NULL::public.v2_race_entries,to_jsonb(e)-'recent_form')).* from public.v2_race_entries e order by race_id,lane) to '/tmp/source_compact.bin' with (format binary)
SQL
PGOPTIONS="$SRC_OPTS" psql "$SOURCE_DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/export_source.sql

echo PARITY_EXPORT_TARGET
cat >/tmp/export_target.sql <<'SQL'
\copy (select e.* from public.v2_race_entries e order by race_id,lane) to '/tmp/target_compact.bin' with (format binary)
SQL
PGOPTIONS="$TGT_OPTS" psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/export_target.sql

source_bytes="$(stat -c %s "$SRC_BIN")"
target_bytes="$(stat -c %s "$TGT_BIN")"
source_sha="$(sha256sum "$SRC_BIN" | awk '{print $1}')"
target_sha="$(sha256sum "$TGT_BIN" | awk '{print $1}')"

echo "PARITY_SOURCE_BINARY_BYTES=$source_bytes"
echo "PARITY_TARGET_BINARY_BYTES=$target_bytes"
echo "PARITY_SOURCE_SHA256=$source_sha"
echo "PARITY_TARGET_SHA256=$target_sha"

test "$source_bytes" = "$target_bytes"
test "$source_sha" = "$target_sha"
cmp -s "$SRC_BIN" "$TGT_BIN"

rm -f "$SRC_BIN" "$TGT_BIN"
echo PARITY_EXACT_MATCH=1
echo PARITY_COMPLETED
