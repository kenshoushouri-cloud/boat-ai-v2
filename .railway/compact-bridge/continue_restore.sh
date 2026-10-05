#!/usr/bin/env bash
set -euo pipefail

: "${SOURCE_DATABASE_URL:?SOURCE_DATABASE_URL required}"

SRC_OPTS="-c default_transaction_read_only=on -c statement_timeout=0 -c work_mem=8MB -c max_parallel_workers_per_gather=0"

echo INDEX_AUDIT_BEGIN
PGOPTIONS="$SRC_OPTS" psql "$SOURCE_DATABASE_URL" -X -v ON_ERROR_STOP=1 -At -F '|' -c "
select
  pg_relation_size(i.indexrelid)::bigint as index_bytes,
  n.nspname,
  t.relname as table_name,
  ci.relname as index_name,
  i.indisunique,
  i.indisprimary,
  pg_get_indexdef(i.indexrelid)
from pg_index i
join pg_class ci on ci.oid=i.indexrelid
join pg_class t on t.oid=i.indrelid
join pg_namespace n on n.oid=t.relnamespace
where n.nspname='public'
order by pg_relation_size(i.indexrelid) desc
limit 30;
"
echo INDEX_AUDIT_END
