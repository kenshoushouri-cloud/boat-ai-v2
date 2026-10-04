# -*- coding: utf-8 -*-
"""Read-only exact-row inventory for core/high-footprint Boat tables.

This exists because pg_stat_user_tables can be stale after recovery/import work.
It performs SELECT/catalog queries only and makes no Production mutation.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


TABLES = (
    'v2_races',
    'v2_race_entries',
    'v2_results',
    'v2_result_entries',
    'v2_previous_st_shadow_rankings',
    'v2_realtime_condition_shadow_rankings',
    'v2_racer_course_shadow_rankings',
)


def one(sql: str):
    rows = fetch_all(sql)
    return dict(rows[0]) if rows else {}


def main() -> None:
    print('STORAGE_CORE_TABLES_MODE=READ_ONLY_NO_MUTATION')
    for table in TABLES:
        catalog = one(
            f"""
            select
              pg_total_relation_size(c.oid) as total_bytes,
              pg_relation_size(c.oid) as heap_bytes,
              pg_indexes_size(c.oid) as index_bytes,
              c.reltuples::bigint as planner_rows,
              coalesce(s.n_live_tup,0)::bigint as stats_live_rows,
              coalesce(s.n_dead_tup,0)::bigint as stats_dead_rows,
              s.last_autovacuum,
              s.last_autoanalyze
            from pg_class c
            left join pg_stat_user_tables s on s.relid=c.oid
            where c.oid='public.{table}'::regclass
            """
        )
        exact = one(f'select count(*)::bigint as exact_rows from {table}')
        exact_rows = int(exact.get('exact_rows') or 0)
        total_bytes = int(catalog.get('total_bytes') or 0)
        bytes_per_row = round(total_bytes / exact_rows, 2) if exact_rows else None
        print(
            'STORAGE_CORE_TABLE='
            f"name:{table} exact_rows:{exact_rows} "
            f"planner_rows:{int(catalog.get('planner_rows') or 0)} "
            f"stats_live:{int(catalog.get('stats_live_rows') or 0)} "
            f"stats_dead:{int(catalog.get('stats_dead_rows') or 0)} "
            f"total_bytes:{total_bytes} heap_bytes:{int(catalog.get('heap_bytes') or 0)} "
            f"index_bytes:{int(catalog.get('index_bytes') or 0)} "
            f"bytes_per_exact_row:{bytes_per_row} "
            f"last_autovacuum:{catalog.get('last_autovacuum')} "
            f"last_autoanalyze:{catalog.get('last_autoanalyze')}"
        )
    print('STORAGE_CORE_TABLES_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
