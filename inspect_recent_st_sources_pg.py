# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")

TARGET_TABLES = [
    "v2_results",
    "v2_race_entries",
    "v2_exhibition",
    "v2_realtime_racer_condition_snapshots",
    "v2_feature_snapshots",
]


def main() -> None:
    print(
        "✅ inspect_recent_st_sources_pg.py "
        "VERSION 2026-07-16 recent-st-source-inspection-v2-percent-fix",
        flush=True,
    )

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print("読み取り専用です。", flush=True)

    rows = fetch_all(
        """
        select
            table_name,
            column_name,
            data_type
        from information_schema.columns
        where table_schema = 'public'
          and table_name like 'v2_%%'
          and (
                lower(column_name) like '%%st%%'
             or lower(column_name) like '%%start%%'
             or lower(column_name) like '%%racer%%'
             or lower(column_name) like '%%lane%%'
          )
        order by table_name, ordinal_position;
        """
    )

    print("=== ST CANDIDATE COLUMNS ===", flush=True)
    for row in rows:
        print(
            f"{row.get('table_name')}.{row.get('column_name')} "
            f"({row.get('data_type')})",
            flush=True,
        )

    for table in TARGET_TABLES:
        exists = fetch_all(
            "select to_regclass(%s) as regclass;",
            (f"public.{table}",),
        )
        if not exists or not exists[0].get("regclass"):
            print(f"=== {table}: NOT FOUND ===", flush=True)
            continue

        columns = fetch_all(
            """
            select column_name, data_type
            from information_schema.columns
            where table_schema = 'public'
              and table_name = %s
            order by ordinal_position;
            """,
            (table,),
        )

        print(f"=== {table} COLUMNS ===", flush=True)
        print(
            ", ".join(
                f"{column.get('column_name')}:{column.get('data_type')}"
                for column in columns
            ),
            flush=True,
        )

    coverage = fetch_all(
        """
        select
            count(*) as rows,
            count(*) filter (
                where previous_st is not null
            ) as previous_st_filled,
            count(distinct race_id) filter (
                where previous_st is not null
            ) as races_with_previous_st,
            min(race_date) filter (
                where previous_st is not null
            ) as min_date,
            max(race_date) filter (
                where previous_st is not null
            ) as max_date
        from v2_realtime_racer_condition_snapshots;
        """
    )

    print("=== PREVIOUS ST STORED COVERAGE ===", flush=True)
    if coverage:
        print(coverage[0], flush=True)

    sample_queries = [
        (
            "v2_results",
            """
            select *
            from v2_results
            where race_id like %s
            order by race_id
            limit 3;
            """,
            (TARGET_DATE.replace("-", "") + "%",),
        ),
        (
            "v2_exhibition",
            """
            select *
            from v2_exhibition
            where race_id like %s
            order by race_id, lane
            limit 12;
            """,
            (TARGET_DATE.replace("-", "") + "%",),
        ),
        (
            "v2_realtime_racer_condition_snapshots",
            """
            select *
            from v2_realtime_racer_condition_snapshots
            where race_date = %s
            order by race_id, lane
            limit 12;
            """,
            (TARGET_DATE,),
        ),
    ]

    for table, sql, params in sample_queries:
        exists = fetch_all(
            "select to_regclass(%s) as regclass;",
            (f"public.{table}",),
        )
        if not exists or not exists[0].get("regclass"):
            continue

        sample_rows = fetch_all(sql, params)
        print(
            f"=== {table} SAMPLE rows={len(sample_rows)} ===",
            flush=True,
        )

        for row in sample_rows:
            filtered = {
                key: value
                for key, value in row.items()
                if (
                    key
                    in {
                        "race_id",
                        "race_date",
                        "venue_id",
                        "venue_code",
                        "race_no",
                        "lane",
                        "racer_number",
                        "result_trifecta",
                        "first_lane",
                        "second_lane",
                        "third_lane",
                    }
                    or "st" in key.lower()
                    or "start" in key.lower()
                    or "finish" in key.lower()
                )
            }
            print(filtered, flush=True)

    print("=== DIAGNOSIS GUIDE ===", flush=True)
    print(
        "v2_resultsに選手別ST列がなければ、結果テーブルだけから"
        "直近3走STは生成できません。",
        flush=True,
    )
    print(
        "v2_exhibitionに選手別STが継続保存されていれば、"
        "race_id・racer_number・laneの結合で生成可能です。",
        flush=True,
    )
    print("=== recent ST source inspection finished ===", flush=True)


if __name__ == "__main__":
    main()