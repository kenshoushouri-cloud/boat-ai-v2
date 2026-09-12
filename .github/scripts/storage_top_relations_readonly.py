# -*- coding: utf-8 -*-
"""Read-only PostgreSQL top-relation inventory for capacity research."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


def main() -> None:
    rows = fetch_all(
        """
        select
          n.nspname as schema_name,
          c.relname as relation_name,
          c.relkind,
          pg_total_relation_size(c.oid) as total_bytes,
          case when c.relkind in ('r','p','m') then pg_relation_size(c.oid) else 0 end as heap_bytes,
          case when c.relkind in ('r','p','m') then pg_indexes_size(c.oid) else 0 end as index_bytes,
          coalesce(s.n_live_tup,0)::bigint as live_rows,
          coalesce(s.n_dead_tup,0)::bigint as dead_rows,
          s.last_autovacuum,
          s.last_autoanalyze
        from pg_class c
        join pg_namespace n on n.oid=c.relnamespace
        left join pg_stat_user_tables s
          on s.relid=c.oid
        where n.nspname not in ('pg_catalog','information_schema')
          and n.nspname not like 'pg_toast%'
          and c.relkind in ('r','p','m')
        order by pg_total_relation_size(c.oid) desc, n.nspname, c.relname
        limit 40
        """
    )
    db = fetch_all(
        """
        select pg_database_size(current_database()) as database_bytes
        """
    )
    db_bytes = int(db[0].get('database_bytes') or 0) if db else 0

    print('STORAGE_TOP_RELATIONS_MODE=READ_ONLY_NO_MUTATION')
    print(f'STORAGE_TOP_RELATIONS_DATABASE_BYTES={db_bytes}')
    for rank, row in enumerate(rows, start=1):
        total = int(row.get('total_bytes') or 0)
        share_bp = int(round(total * 10000 / db_bytes)) if db_bytes else 0
        print(
            'STORAGE_TOP_RELATION='
            f"rank:{rank} schema:{row.get('schema_name')} name:{row.get('relation_name')} "
            f"kind:{row.get('relkind')} total_bytes:{total} "
            f"heap_bytes:{int(row.get('heap_bytes') or 0)} "
            f"index_bytes:{int(row.get('index_bytes') or 0)} "
            f"share_basis_points:{share_bp} "
            f"live_rows:{int(row.get('live_rows') or 0)} dead_rows:{int(row.get('dead_rows') or 0)} "
            f"last_autovacuum:{row.get('last_autovacuum')} last_autoanalyze:{row.get('last_autoanalyze')}"
        )
    print('STORAGE_TOP_RELATIONS_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
