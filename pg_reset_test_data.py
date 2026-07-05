# -*- coding: utf-8 -*-
"""
pg_reset_test_data.py

Railway Postgres版のテストデータ初期化用。
v2_venues の24場マスタは残し、テスト中に入ったレース・出走表・結果・オッズ等を削除します。

Railway Start Command:
    python pg_reset_test_data.py

安全装置:
    PG_RESET_CONFIRM=YES
を設定していない場合は停止します。
"""

import os
import psycopg


TABLES_TO_TRUNCATE = [
    "v2_races",
    "v2_race_entries",
    "v2_results",
    "v2_odds_trifecta",
    "v2_realtime_odds_snapshots",
    "v2_exhibition",
    "v2_race_weather",
    "v2_feature_snapshots",
    "v2_realtime_decisions",
    "v2_learning_daily_reports",
    "v2_line_notifications",
    "pg_health_check",
]


def table_exists(cur, table_name: str) -> bool:
    cur.execute(
        """
        select exists (
            select 1
            from information_schema.tables
            where table_schema = 'public'
              and table_name = %s
        );
        """,
        (table_name,),
    )
    return bool(cur.fetchone()[0])


def count_rows(cur, table_name: str) -> int:
    cur.execute(f"select count(*) from public.{table_name};")
    return int(cur.fetchone()[0])


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    confirm = os.environ.get("PG_RESET_CONFIRM")
    if confirm != "YES":
        raise RuntimeError("安全装置: PG_RESET_CONFIRM=YES を設定してから実行してください。")

    print("=== Railway Postgres test data reset ===", flush=True)
    print("DATABASE_URL: found", flush=True)
    print("PG_RESET_CONFIRM=YES", flush=True)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            print("--- before ---", flush=True)
            existing_tables = []
            for table in TABLES_TO_TRUNCATE:
                if table_exists(cur, table):
                    existing_tables.append(table)
                    print(f"{table}: rows={count_rows(cur, table)}", flush=True)
                else:
                    print(f"{table}: missing - skip", flush=True)

            if table_exists(cur, "v2_venues"):
                print(f"v2_venues: rows={count_rows(cur, 'v2_venues')}", flush=True)

            # データ系テーブルを初期化
            for table in existing_tables:
                cur.execute(f"truncate table public.{table} restart identity cascade;")
                print(f"truncated: {table}", flush=True)

            # テスト用 venue 99 だけ削除。24場マスタは残す。
            if table_exists(cur, "v2_venues"):
                cur.execute(
                    """
                    delete from public.v2_venues
                    where venue_code = '99'
                       or venue_id = '99';
                    """
                )
                print("deleted test venue: 99", flush=True)

            conn.commit()

        with conn.cursor() as cur:
            print("--- after ---", flush=True)
            for table in TABLES_TO_TRUNCATE:
                if table_exists(cur, table):
                    print(f"{table}: rows={count_rows(cur, table)}", flush=True)

            if table_exists(cur, "v2_venues"):
                print(f"v2_venues: rows={count_rows(cur, 'v2_venues')}", flush=True)

    print("=== reset finished ===", flush=True)


if __name__ == "__main__":
    main()