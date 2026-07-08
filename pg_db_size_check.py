# -*- coding: utf-8 -*-
"""
pg_db_size_check.py

Railway Postgres DB容量・テーブル別サイズ確認。

Railway Start Command:
    python -u pg_db_size_check.py
"""

from __future__ import annotations

import os
from db_pg import fetch_all, fetch_one


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("=== PG database size check ===", flush=True)

    db = fetch_one(
        "select pg_size_pretty(pg_database_size(current_database())) as db_size;"
    )
    print(f"database_size: {db.get('db_size')}", flush=True)

    rows = fetch_all(
        """
        select
          relname as table_name,
          pg_size_pretty(pg_total_relation_size(relid)) as total_size,
          pg_total_relation_size(relid) as bytes
        from pg_catalog.pg_statio_user_tables
        order by pg_total_relation_size(relid) desc
        limit 30;
        """
    )

    print("\n--- table sizes top 30 ---", flush=True)
    for r in rows:
        print(f"{r['table_name']}: {r['total_size']}", flush=True)

    print("=== size check finished ===", flush=True)


if __name__ == "__main__":
    main()