# -*- coding: utf-8 -*-
"""Read-only index inventory for v2_realtime_odds_snapshots.

Capacity research only. Reports physical index bytes, key columns, constraint
ownership, usage counters, and exact index definitions. No schema mutation.
"""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all

TABLE = "v2_realtime_odds_snapshots"


def rows(sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    return [dict(row) for row in fetch_all(sql, params or ())]


def one(sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any]:
    data = rows(sql, params)
    return data[0] if data else {}


def main() -> None:
    print("STORAGE_RT_ODDS_INDEX_MODE=READ_ONLY_NO_SCHEMA_CHANGE")

    size = one(
        """
        select pg_total_relation_size(%s::regclass)::bigint as total_bytes,
               pg_relation_size(%s::regclass)::bigint as heap_bytes,
               pg_indexes_size(%s::regclass)::bigint as index_bytes
        """,
        (f"public.{TABLE}", f"public.{TABLE}", f"public.{TABLE}"),
    )
    print(
        "STORAGE_RT_ODDS_RELATION="
        f"total_bytes:{int(size.get('total_bytes') or 0)} "
        f"heap_bytes:{int(size.get('heap_bytes') or 0)} "
        f"index_bytes:{int(size.get('index_bytes') or 0)}"
    )

    reset = one(
        """
        select stats_reset
          from pg_stat_database
         where datname=current_database()
        """
    )
    print(f"STORAGE_RT_ODDS_INDEX_STATS_RESET={reset.get('stats_reset')}")

    index_rows = rows(
        """
        with keys as (
          select i.indexrelid,
                 array_agg(a.attname order by u.ord)
                   filter (where u.ord <= i.indnkeyatts) as key_columns
            from pg_index i
            cross join lateral unnest(i.indkey) with ordinality as u(attnum,ord)
            left join pg_attribute a
              on a.attrelid=i.indrelid and a.attnum=u.attnum
           where i.indrelid=%s::regclass
           group by i.indexrelid
        ), constraint_owner as (
          select conindid,
                 string_agg(conname || ':' || contype::text, ',' order by conname) as constraints
            from pg_constraint
           where conindid <> 0
           group by conindid
        )
        select s.indexrelname as index_name,
               pg_relation_size(s.indexrelid)::bigint as bytes,
               i.indisunique as is_unique,
               i.indisprimary as is_primary,
               i.indisvalid as is_valid,
               i.indisready as is_ready,
               i.indislive as is_live,
               am.amname as access_method,
               coalesce(k.key_columns,array[]::text[]) as key_columns,
               coalesce(co.constraints,'') as constraints,
               s.idx_scan::bigint as idx_scan,
               s.idx_tup_read::bigint as idx_tup_read,
               s.idx_tup_fetch::bigint as idx_tup_fetch,
               pg_get_indexdef(s.indexrelid) as index_def
          from pg_stat_user_indexes s
          join pg_index i on i.indexrelid=s.indexrelid
          join pg_class c on c.oid=s.indexrelid
          join pg_am am on am.oid=c.relam
          left join keys k on k.indexrelid=s.indexrelid
          left join constraint_owner co on co.conindid=s.indexrelid
         where s.schemaname='public'
           and s.relname=%s
         order by pg_relation_size(s.indexrelid) desc
        """,
        (f"public.{TABLE}", TABLE),
    )

    parsed: list[dict[str, Any]] = []
    for item in index_rows:
        columns = tuple(str(value) for value in (item.get("key_columns") or []))
        definition = str(item.get("index_def") or "").replace("\n", " ").strip()
        parsed.append({**item, "columns": columns})
        print(
            "STORAGE_RT_ODDS_INDEX="
            f"name:{item.get('index_name')} "
            f"bytes:{int(item.get('bytes') or 0)} "
            f"unique:{str(bool(item.get('is_unique'))).lower()} "
            f"primary:{str(bool(item.get('is_primary'))).lower()} "
            f"valid:{str(bool(item.get('is_valid'))).lower()} "
            f"ready:{str(bool(item.get('is_ready'))).lower()} "
            f"live:{str(bool(item.get('is_live'))).lower()} "
            f"method:{item.get('access_method')} "
            f"columns:{','.join(columns)} "
            f"constraints:{item.get('constraints') or '-'} "
            f"idx_scan:{int(item.get('idx_scan') or 0)} "
            f"idx_tup_read:{int(item.get('idx_tup_read') or 0)} "
            f"idx_tup_fetch:{int(item.get('idx_tup_fetch') or 0)}"
        )
        print(
            "STORAGE_RT_ODDS_INDEX_RECREATE="
            f"name:{item.get('index_name')} definition:{definition}"
        )

    for short in parsed:
        short_columns = short["columns"]
        if not short_columns:
            continue
        for long in parsed:
            if short is long:
                continue
            long_columns = long["columns"]
            if (
                short.get("access_method") == "btree"
                and long.get("access_method") == "btree"
                and len(long_columns) > len(short_columns)
                and long_columns[: len(short_columns)] == short_columns
            ):
                print(
                    "STORAGE_RT_ODDS_INDEX_PREFIX_RELATION="
                    f"short:{short.get('index_name')} "
                    f"short_bytes:{int(short.get('bytes') or 0)} "
                    f"short_scans:{int(short.get('idx_scan') or 0)} "
                    f"long:{long.get('index_name')} "
                    f"long_bytes:{int(long.get('bytes') or 0)} "
                    f"long_scans:{int(long.get('idx_scan') or 0)} "
                    f"prefix_columns:{','.join(short_columns)} "
                    "structurally_subsumed:true performance_equivalent:not_proven"
                )

    print(f"STORAGE_RT_ODDS_INDEX_COUNT={len(parsed)}")
    print(
        "STORAGE_RT_ODDS_INDEX_TOTAL_BYTES="
        f"{sum(int(item.get('bytes') or 0) for item in parsed)}"
    )
    print("STORAGE_RT_ODDS_INDEX_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
