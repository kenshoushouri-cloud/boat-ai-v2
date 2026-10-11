# -*- coding: utf-8 -*-
"""Read-only PostgreSQL reclaim-planning stats for Motor2 shadow.

No DELETE, VACUUM, ANALYZE, DDL, or other mutation is executed here.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


def one(sql: str) -> dict:
    rows = fetch_all(sql)
    return dict(rows[0]) if rows else {}


def main() -> None:
    stats = one(
        """
        select
          schemaname,
          relname,
          n_live_tup,
          n_dead_tup,
          n_mod_since_analyze,
          last_vacuum,
          last_autovacuum,
          vacuum_count,
          autovacuum_count,
          last_analyze,
          last_autoanalyze,
          analyze_count,
          autoanalyze_count
        from pg_stat_user_tables
        where relname = 'v2_v24_motor2_forward_shadow'
        """
    )
    relation = one(
        """
        select
          pg_total_relation_size('v2_v24_motor2_forward_shadow') as total_bytes,
          pg_relation_size('v2_v24_motor2_forward_shadow') as heap_bytes,
          pg_indexes_size('v2_v24_motor2_forward_shadow') as index_bytes,
          c.relpages,
          c.reltuples::bigint as planner_rows
        from pg_class c
        where c.oid = 'v2_v24_motor2_forward_shadow'::regclass
        """
    )
    db = one(
        """
        select
          pg_database_size(current_database()) as database_bytes,
          current_setting('autovacuum') as autovacuum_setting
        """
    )

    print('STORAGE_RECLAIM_STATS_MODE=READ_ONLY_NO_VACUUM_NO_DELETE')
    print(
        'STORAGE_RECLAIM_TABLE_STATS='
        f"live:{int(stats.get('n_live_tup') or 0)} "
        f"dead:{int(stats.get('n_dead_tup') or 0)} "
        f"modified_since_analyze:{int(stats.get('n_mod_since_analyze') or 0)} "
        f"last_vacuum:{stats.get('last_vacuum')} "
        f"last_autovacuum:{stats.get('last_autovacuum')} "
        f"vacuum_count:{int(stats.get('vacuum_count') or 0)} "
        f"autovacuum_count:{int(stats.get('autovacuum_count') or 0)}"
    )
    print(
        'STORAGE_RECLAIM_ANALYZE_STATS='
        f"last_analyze:{stats.get('last_analyze')} "
        f"last_autoanalyze:{stats.get('last_autoanalyze')} "
        f"analyze_count:{int(stats.get('analyze_count') or 0)} "
        f"autoanalyze_count:{int(stats.get('autoanalyze_count') or 0)}"
    )
    print(
        'STORAGE_RECLAIM_RELATION='
        f"total_bytes:{int(relation.get('total_bytes') or 0)} "
        f"heap_bytes:{int(relation.get('heap_bytes') or 0)} "
        f"index_bytes:{int(relation.get('index_bytes') or 0)} "
        f"relpages:{int(relation.get('relpages') or 0)} "
        f"planner_rows:{int(relation.get('planner_rows') or 0)}"
    )
    print(
        'STORAGE_RECLAIM_DATABASE='
        f"database_bytes:{int(db.get('database_bytes') or 0)} "
        f"autovacuum:{db.get('autovacuum_setting')}"
    )
    print('STORAGE_RECLAIM_STATS_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
