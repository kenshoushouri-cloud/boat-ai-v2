# -*- coding: utf-8 -*-
"""Read-only structural/usage audit for indexes on v2_odds_trifecta.

Capacity research only. Reports index definitions, sizes, usage counters,
constraint ownership, and planner choices for representative SELECT shapes.
It performs no schema change.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


def rows(sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    return [dict(r) for r in fetch_all(sql, params or ())]


def one(sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any]:
    data = rows(sql, params)
    return data[0] if data else {}


def _index_names_from_plan(value: Any) -> list[str]:
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            name = node.get("Index Name")
            if name:
                found.append(str(name))
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return sorted(set(found))


def _plan_indexes(sql: str, params: tuple[Any, ...]) -> list[str]:
    result = fetch_all("EXPLAIN (FORMAT JSON) " + sql, params)
    if not result:
        return []
    raw = next(iter(dict(result[0]).values()), None)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    return _index_names_from_plan(raw)


def main() -> None:
    print("STORAGE_ODDS_INDEX_MODE=READ_ONLY_NO_SCHEMA_CHANGE")

    reset = one(
        """
        select stats_reset
          from pg_stat_database
         where datname=current_database()
        """
    )
    print(f"STORAGE_ODDS_INDEX_STATS_RESET={reset.get('stats_reset')}")

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
           where i.indrelid='public.v2_odds_trifecta'::regclass
           group by i.indexrelid
        ), constraint_owner as (
          select conindid,
                 string_agg(conname || ':' || contype, ',' order by conname) as constraints
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
           and s.relname='v2_odds_trifecta'
         order by pg_relation_size(s.indexrelid) desc
        """
    )

    parsed: list[dict[str, Any]] = []
    for item in index_rows:
        cols = tuple(str(x) for x in (item.get("key_columns") or []))
        parsed.append({**item, "cols": cols})
        print(
            "STORAGE_ODDS_INDEX="
            f"name:{item.get('index_name')} "
            f"bytes:{int(item.get('bytes') or 0)} "
            f"unique:{str(bool(item.get('is_unique'))).lower()} "
            f"primary:{str(bool(item.get('is_primary'))).lower()} "
            f"valid:{str(bool(item.get('is_valid'))).lower()} "
            f"ready:{str(bool(item.get('is_ready'))).lower()} "
            f"live:{str(bool(item.get('is_live'))).lower()} "
            f"method:{item.get('access_method')} "
            f"columns:{','.join(cols)} "
            f"constraints:{item.get('constraints') or '-'} "
            f"idx_scan:{int(item.get('idx_scan') or 0)} "
            f"idx_tup_read:{int(item.get('idx_tup_read') or 0)} "
            f"idx_tup_fetch:{int(item.get('idx_tup_fetch') or 0)}"
        )

    for left in parsed:
        left_cols = left["cols"]
        if not left_cols:
            continue
        for right in parsed:
            if left is right:
                continue
            right_cols = right["cols"]
            if (
                left.get("access_method") == "btree"
                and right.get("access_method") == "btree"
                and len(right_cols) > len(left_cols)
                and right_cols[: len(left_cols)] == left_cols
            ):
                print(
                    "STORAGE_ODDS_INDEX_PREFIX_RELATION="
                    f"short:{left.get('index_name')} "
                    f"short_bytes:{int(left.get('bytes') or 0)} "
                    f"short_scans:{int(left.get('idx_scan') or 0)} "
                    f"long:{right.get('index_name')} "
                    f"long_bytes:{int(right.get('bytes') or 0)} "
                    f"long_scans:{int(right.get('idx_scan') or 0)} "
                    f"prefix_columns:{','.join(left_cols)} "
                    "structurally_subsumed:true performance_equivalent:not_proven"
                )

    sample = one(
        """
        select max(race_id) as race_id,
               min(race_id) as min_race_id,
               max(race_date) as race_date,
               min(race_date) as min_race_date
          from v2_odds_trifecta
        """
    )
    race_id = str(sample.get("race_id") or "")
    min_race_id = str(sample.get("min_race_id") or "")
    race_date = sample.get("race_date")
    min_race_date = sample.get("min_race_date")
    shapes: list[tuple[str, str, tuple[Any, ...]]] = []
    if race_id:
        shapes.extend(
            (
                (
                    "race_id_equality_order_ticket",
                    "select race_id,ticket,odds from v2_odds_trifecta where race_id=%s order by race_id,ticket",
                    (race_id,),
                ),
                (
                    "race_id_equality_count",
                    "select count(*) from v2_odds_trifecta where race_id=%s",
                    (race_id,),
                ),
                (
                    "race_id_range_order_ticket",
                    "select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id <= %s order by race_id,ticket",
                    (min_race_id, race_id),
                ),
            )
        )
    if race_date is not None:
        shapes.extend(
            (
                (
                    "race_date_equality_count",
                    "select count(*) from v2_odds_trifecta where race_date=%s",
                    (race_date,),
                ),
                (
                    "race_date_equality_rows",
                    "select race_id,ticket,odds from v2_odds_trifecta where race_date=%s",
                    (race_date,),
                ),
                (
                    "race_date_range_count",
                    "select count(*) from v2_odds_trifecta where race_date >= %s and race_date <= %s",
                    (min_race_date, race_date),
                ),
            )
        )
    for name, sql, params in shapes:
        indexes = _plan_indexes(sql, params)
        print(
            "STORAGE_ODDS_INDEX_PLAN="
            f"shape:{name} indexes:{','.join(indexes) if indexes else 'none'}"
        )

    total_index_bytes = sum(int(x.get("bytes") or 0) for x in parsed)
    print(f"STORAGE_ODDS_INDEX_TOTAL_BYTES={total_index_bytes}")
    print("STORAGE_ODDS_INDEX_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
