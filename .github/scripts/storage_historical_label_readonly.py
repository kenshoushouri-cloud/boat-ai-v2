# -*- coding: utf-8 -*-
"""Read-only inventory for historical realtime snapshot labels.

Capacity research only. This measures logical tuple payload for historical rows in
realtime snapshot tables. It does not claim that deleting those rows would reclaim
the same number of Railway volume bytes. No mutation or schema change is performed.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


TABLES = (
    "v2_realtime_weather_snapshots",
    "v2_realtime_exhibition_snapshots",
    "v2_realtime_race_condition_snapshots",
    "v2_realtime_racer_condition_snapshots",
)


def one(sql: str):
    rows = fetch_all(sql)
    return dict(rows[0]) if rows else {}


def main() -> None:
    print("STORAGE_HISTORICAL_LABEL_MODE=READ_ONLY_NO_MUTATION")
    total_rows = 0
    total_logical = 0
    total_relation = 0

    for table in TABLES:
        row = one(
            f"""
            select count(*)::bigint as rows,
                   count(distinct race_id)::bigint as races,
                   min(race_date) as min_date,
                   max(race_date) as max_date,
                   coalesce(sum(pg_column_size(t)),0)::bigint as logical_bytes,
                   pg_total_relation_size('public.{table}'::regclass)::bigint as relation_bytes
              from public.{table} t
             where snapshot_label='historical'
            """
        )
        rows = int(row.get("rows") or 0)
        logical = int(row.get("logical_bytes") or 0)
        relation = int(row.get("relation_bytes") or 0)
        total_rows += rows
        total_logical += logical
        total_relation += relation
        print(
            "STORAGE_HISTORICAL_LABEL_TABLE="
            f"name:{table} rows:{rows} races:{int(row.get('races') or 0)} "
            f"min_date:{row.get('min_date')} max_date:{row.get('max_date')} "
            f"logical_bytes:{logical} relation_bytes:{relation}"
        )

    print(
        "STORAGE_HISTORICAL_LABEL_TOTAL="
        f"rows:{total_rows} logical_bytes:{total_logical} "
        f"relation_bytes_sum:{total_relation}"
    )
    print("STORAGE_HISTORICAL_LABEL_INTERPRETATION=LOGICAL_PAYLOAD_NOT_PHYSICAL_RECLAIM")
    print("STORAGE_HISTORICAL_LABEL_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
