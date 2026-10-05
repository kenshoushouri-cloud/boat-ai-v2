#!/usr/bin/env bash
set -euo pipefail

: "${SOURCE_DATABASE_URL:?SOURCE_DATABASE_URL required}"
: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL required}"

SRC_OPTS="-c default_transaction_read_only=on -c statement_timeout=0 -c work_mem=8MB -c max_parallel_workers_per_gather=0"
BIN_FILE="/tmp/race_entries_compact.bin"
POST_ARCHIVE="/tmp/post_data.dump"
POST_LIST="/tmp/post_data.list"
POST_FILTERED="/tmp/post_data.filtered.list"

echo COMPACT_CONTINUE_PREFLIGHT

target_rows="$(psql "$TARGET_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select count(*) from public.v2_race_entries;")"
echo "COMPACT_CONTINUE_TARGET_RACE_ROWS=$target_rows"
test "$target_rows" = "0"

valid_large_indexes="$(psql "$TARGET_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "
select count(*)
from pg_index i
join pg_class c on c.oid=i.indexrelid
join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public'
  and c.relname in (
    'ux_v2_odds_trifecta_race_ticket',
    'v2_odds_trifecta_pkey',
    'uq_v2_rt_odds_race_label_ticket',
    'idx_v2_odds_race_id',
    'v2_realtime_odds_snapshots_pkey',
    'v2_race_entries_race_id_lane_key',
    'uq_v2_rt_exh_race_label_lane',
    'v2_race_entries_pkey'
  )
  and i.indisvalid
  and i.indisready;
")"
echo "COMPACT_CONTINUE_VALID_LARGE_INDEXES=$valid_large_indexes"
test "$valid_large_indexes" = "8"

existing_constraints="$(psql "$TARGET_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "
select count(*)
from pg_constraint
where conname in (
  'v2_odds_trifecta_pkey',
  'v2_realtime_odds_snapshots_pkey',
  'v2_race_entries_race_id_lane_key',
  'v2_race_entries_pkey'
);
")"
echo "COMPACT_CONTINUE_EXISTING_EARLY_CONSTRAINTS=$existing_constraints"
test "$existing_constraints" = "0"

echo COMPACT_CONTINUE_RACE_EXPORT
cat > /tmp/export_race_entries.sql <<'SQL'
\copy (select (jsonb_populate_record(NULL::public.v2_race_entries,to_jsonb(e)-'recent_form')).* from public.v2_race_entries e order by race_id,lane) to '/tmp/race_entries_compact.bin' with (format binary)
SQL
PGOPTIONS="$SRC_OPTS" psql "$SOURCE_DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/export_race_entries.sql
test -s "$BIN_FILE"
stat -c 'COMPACT_BINARY_BYTES=%s' "$BIN_FILE"

echo COMPACT_CONTINUE_RACE_IMPORT
cat > /tmp/import_race_entries.sql <<'SQL'
\copy public.v2_race_entries from '/tmp/race_entries_compact.bin' with (format binary)
SQL
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/import_race_entries.sql
rm -f "$BIN_FILE"

source_rows="$(PGOPTIONS="$SRC_OPTS" psql "$SOURCE_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select count(*) from public.v2_race_entries;")"
target_rows_after="$(psql "$TARGET_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select count(*) from public.v2_race_entries;")"
echo "COMPACT_CONTINUE_SOURCE_RACE_ROWS=$source_rows"
echo "COMPACT_CONTINUE_TARGET_RACE_ROWS_AFTER=$target_rows_after"
test "$source_rows" = "$target_rows_after"

echo COMPACT_CONTINUE_ATTACH_CONSTRAINTS
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
ALTER TABLE ONLY public.v2_odds_trifecta
  ADD CONSTRAINT v2_odds_trifecta_pkey PRIMARY KEY USING INDEX v2_odds_trifecta_pkey;
ALTER TABLE ONLY public.v2_realtime_odds_snapshots
  ADD CONSTRAINT v2_realtime_odds_snapshots_pkey PRIMARY KEY USING INDEX v2_realtime_odds_snapshots_pkey;
ALTER TABLE ONLY public.v2_race_entries
  ADD CONSTRAINT v2_race_entries_race_id_lane_key UNIQUE USING INDEX v2_race_entries_race_id_lane_key;
ALTER TABLE ONLY public.v2_race_entries
  ADD CONSTRAINT v2_race_entries_pkey PRIMARY KEY USING INDEX v2_race_entries_pkey;
SQL

echo COMPACT_CONTINUE_POST_DATA_PREPARE
PGOPTIONS="$SRC_OPTS" pg_dump "$SOURCE_DATABASE_URL" \
  --schema-only --section=post-data --no-owner --no-acl --format=custom \
  --file="$POST_ARCHIVE"

pg_restore --list "$POST_ARCHIVE" > "$POST_LIST"

grep -Ev 'ux_v2_odds_trifecta_race_ticket|v2_odds_trifecta_pkey|uq_v2_rt_odds_race_label_ticket|idx_v2_odds_race_id|v2_realtime_odds_snapshots_pkey|v2_race_entries_race_id_lane_key|uq_v2_rt_exh_race_label_lane|v2_race_entries_pkey' \
  "$POST_LIST" > "$POST_FILTERED"

echo COMPACT_CONTINUE_POST_DATA
PGOPTIONS="-c maintenance_work_mem=64MB -c max_parallel_maintenance_workers=0" \
  pg_restore --exit-on-error --no-owner --no-acl \
  --use-list="$POST_FILTERED" \
  --dbname="$TARGET_DATABASE_URL" \
  "$POST_ARCHIVE"

rm -f "$POST_ARCHIVE" "$POST_LIST" "$POST_FILTERED"
echo COMPACT_CONTINUE_COMPLETED
