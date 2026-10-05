#!/usr/bin/env bash
set -euo pipefail

: "${SOURCE_DATABASE_URL:?SOURCE_DATABASE_URL required}"
: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL required}"

SRC_OPTS="-c default_transaction_read_only=on -c statement_timeout=0 -c work_mem=8MB -c max_parallel_workers_per_gather=0"
BIN_FILE="/tmp/race_entries_compact.bin"
POST_ARCHIVE="/tmp/post_data.dump"
POST_LIST="/tmp/post_data.list"
POST_FILTERED="/tmp/post_data.filtered.list"

echo COMPACT_FULL_PREFLIGHT
unexpected="$(psql "$TARGET_DATABASE_URL" -At -v ON_ERROR_STOP=1 -c "select count(*) from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind in ('r','p','v','m','S','f') and c.relname <> 'pg_health_check';")"
echo "COMPACT_TARGET_UNEXPECTED_PUBLIC_OBJECTS=$unexpected"
test "$unexpected" = "0"

echo COMPACT_FULL_PRE_DATA
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -c "drop table if exists public.pg_health_check cascade;"
PGOPTIONS="$SRC_OPTS" pg_dump "$SOURCE_DATABASE_URL" \
  --schema-only --section=pre-data --no-owner --no-acl \
  | psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1

echo COMPACT_LARGE_INDEXES_EARLY
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
CREATE UNIQUE INDEX ux_v2_odds_trifecta_race_ticket ON public.v2_odds_trifecta USING btree (race_id, ticket);
CREATE UNIQUE INDEX v2_odds_trifecta_pkey ON public.v2_odds_trifecta USING btree (id);
CREATE UNIQUE INDEX uq_v2_rt_odds_race_label_ticket ON public.v2_realtime_odds_snapshots USING btree (race_id, snapshot_label, ticket);
CREATE INDEX idx_v2_odds_race_id ON public.v2_odds_trifecta USING btree (race_id);
CREATE UNIQUE INDEX v2_realtime_odds_snapshots_pkey ON public.v2_realtime_odds_snapshots USING btree (id);
CREATE UNIQUE INDEX v2_race_entries_race_id_lane_key ON public.v2_race_entries USING btree (race_id, lane);
CREATE UNIQUE INDEX uq_v2_rt_exh_race_label_lane ON public.v2_realtime_exhibition_snapshots USING btree (race_id, snapshot_label, lane);
CREATE UNIQUE INDEX v2_race_entries_pkey ON public.v2_race_entries USING btree (id);
SQL

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

echo COMPACT_ATTACH_EARLY_CONSTRAINTS
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

echo COMPACT_FULL_POST_DATA_PREPARE
PGOPTIONS="$SRC_OPTS" pg_dump "$SOURCE_DATABASE_URL" \
  --schema-only --section=post-data --no-owner --no-acl --format=custom \
  --file="$POST_ARCHIVE"

pg_restore --list "$POST_ARCHIVE" > "$POST_LIST"

grep -Ev 'ux_v2_odds_trifecta_race_ticket|v2_odds_trifecta_pkey|uq_v2_rt_odds_race_label_ticket|idx_v2_odds_race_id|v2_realtime_odds_snapshots_pkey|v2_race_entries_race_id_lane_key|uq_v2_rt_exh_race_label_lane|v2_race_entries_pkey' \
  "$POST_LIST" > "$POST_FILTERED"

for object_name in \
  ux_v2_odds_trifecta_race_ticket \
  v2_odds_trifecta_pkey \
  uq_v2_rt_odds_race_label_ticket \
  idx_v2_odds_race_id \
  v2_realtime_odds_snapshots_pkey \
  v2_race_entries_race_id_lane_key \
  uq_v2_rt_exh_race_label_lane \
  v2_race_entries_pkey
do
  test "$(grep -c "$object_name" "$POST_FILTERED" || true)" = "0"
done

echo COMPACT_FULL_POST_DATA
PGOPTIONS="-c maintenance_work_mem=64MB -c max_parallel_maintenance_workers=0" \
  pg_restore --exit-on-error --no-owner --no-acl \
  --use-list="$POST_FILTERED" \
  --dbname="$TARGET_DATABASE_URL" \
  "$POST_ARCHIVE"

rm -f "$POST_ARCHIVE" "$POST_LIST" "$POST_FILTERED"
echo COMPACT_FULL_COMPLETED
