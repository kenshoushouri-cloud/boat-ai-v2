# -*- coding: utf-8 -*-
"""Read-only Production schema/footprint preflight for a future fresh restore rehearsal.

This script reads PostgreSQL catalog metadata only. It does not copy table rows,
change retention, create schema, or mutate Production.
"""
from __future__ import annotations

import os
from collections import defaultdict

from db_pg import fetch_all, fetch_one


RETENTION_HINT_COLUMNS = {
    "race_id",
    "race_date",
    "snapshot_label",
    "snapshot_at",
    "created_at",
    "updated_at",
    "target_date",
    "deadline_at",
    "deadline_time",
    "run_class",
    "window_name",
}


def _truthy(v: object) -> bool:
    return str(v or "").strip().lower() in {"on", "true", "1", "yes"}


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    ro = fetch_one("select current_setting('transaction_read_only') as read_only") or {}
    if not _truthy(ro.get("read_only")):
        raise RuntimeError("default_transaction_read_only must be on")

    db = fetch_one(
        """
        select pg_database_size(current_database())::bigint as db_bytes,
               current_database()::text as db_name
        """
    ) or {}

    tables = fetch_all(
        """
        select c.relname::text as table_name,
               greatest(c.reltuples,0)::bigint as estimated_rows,
               pg_relation_size(c.oid)::bigint as heap_bytes,
               pg_indexes_size(c.oid)::bigint as index_bytes,
               pg_total_relation_size(c.oid)::bigint as total_bytes
        from pg_class c
        join pg_namespace n on n.oid=c.relnamespace
        where n.nspname='public'
          and c.relkind in ('r','p')
        order by pg_total_relation_size(c.oid) desc, c.relname
        """
    )

    columns = fetch_all(
        """
        select c.relname::text as table_name,
               a.attname::text as column_name,
               format_type(a.atttypid,a.atttypmod)::text as data_type
        from pg_class c
        join pg_namespace n on n.oid=c.relnamespace
        join pg_attribute a on a.attrelid=c.oid
        where n.nspname='public'
          and c.relkind in ('r','p')
          and a.attnum>0
          and not a.attisdropped
        order by c.relname,a.attnum
        """
    )

    pks = fetch_all(
        """
        select tc.table_name::text as table_name,
               kcu.column_name::text as column_name,
               kcu.ordinal_position::int as ordinal_position
        from information_schema.table_constraints tc
        join information_schema.key_column_usage kcu
          on kcu.constraint_name=tc.constraint_name
         and kcu.constraint_schema=tc.constraint_schema
         and kcu.table_name=tc.table_name
        where tc.constraint_schema='public'
          and tc.constraint_type='PRIMARY KEY'
        order by tc.table_name,kcu.ordinal_position
        """
    )

    hints: dict[str, list[str]] = defaultdict(list)
    column_counts: dict[str, int] = defaultdict(int)
    for row in columns:
        table = str(row.get("table_name") or "")
        col = str(row.get("column_name") or "")
        column_counts[table] += 1
        if col in RETENTION_HINT_COLUMNS:
            hints[table].append(f"{col}:{row.get('data_type')}")

    pk_map: dict[str, list[str]] = defaultdict(list)
    for row in pks:
        pk_map[str(row.get("table_name") or "")].append(str(row.get("column_name") or ""))

    total_rel = sum(int(r.get("total_bytes") or 0) for r in tables)
    total_heap = sum(int(r.get("heap_bytes") or 0) for r in tables)
    total_index = sum(int(r.get("index_bytes") or 0) for r in tables)

    print("FRESH_RESTORE_SCHEMA_PREFLIGHT=READ_ONLY", flush=True)
    print(
        "DATABASE "
        f"db_bytes={int(db.get('db_bytes') or 0)} "
        f"table_count={len(tables)} "
        f"user_relation_bytes={total_rel} "
        f"user_heap_bytes={total_heap} "
        f"user_index_bytes={total_index}",
        flush=True,
    )

    for row in tables:
        name = str(row.get("table_name") or "")
        hint_text = ",".join(hints.get(name, [])) or "none"
        pk_text = ",".join(pk_map.get(name, [])) or "none"
        total = int(row.get("total_bytes") or 0)
        heap = int(row.get("heap_bytes") or 0)
        indexes = int(row.get("index_bytes") or 0)
        other = max(0, total - heap - indexes)
        print(
            "TABLE "
            f"name={name} "
            f"est_rows={int(row.get('estimated_rows') or 0)} "
            f"columns={column_counts.get(name,0)} "
            f"heap_bytes={heap} index_bytes={indexes} other_bytes={other} total_bytes={total} "
            f"pk={pk_text} retention_hints={hint_text}",
            flush=True,
        )

    no_hint = [str(r.get("table_name") or "") for r in tables if not hints.get(str(r.get("table_name") or ""))]
    print(f"NO_RETENTION_HINT_TABLES count={len(no_hint)} names={','.join(no_hint)}", flush=True)
    print("PREFLIGHT_NOTE=no_row_copy_no_mutation_no_retention_decision", flush=True)
    print("FRESH_RESTORE_SCHEMA_PREFLIGHT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
