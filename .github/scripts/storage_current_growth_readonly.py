# -*- coding: utf-8 -*-
"""Read-only recent growth inventory for major actively growing Boat tables.

Uses the latest seven completed race/snapshot dates (current_date-7 through
current_date-1) and reports logical tuple bytes. Logical bytes are a comparison
metric only; they are not guaranteed physical Railway-volume reclaim.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


# table, date expression, optional read-only join used only to resolve the date.
# v2_odds_trifecta's own race_date is not a reliable populated key, so its date
# must be resolved from v2_races exactly as the existing odds inventory does.
TABLES = (
    ("v2_odds_trifecta", "r.race_date", "join public.v2_races r on r.race_id=t.race_id"),
    ("v2_realtime_odds_snapshots", "t.race_date", ""),
    ("v2_realtime_weather_snapshots", "t.race_date", ""),
    ("v2_realtime_exhibition_snapshots", "t.race_date", ""),
    ("v2_realtime_entry_snapshots", "t.race_date", ""),
    ("v2_realtime_race_condition_snapshots", "t.race_date", ""),
    ("v2_realtime_racer_condition_snapshots", "t.race_date", ""),
    ("v2_v24_motor2_forward_shadow", "t.race_date", ""),
    ("v2_racer_course_stats_snapshots", "t.snapshot_date", ""),
    ("v2_opponent_pressure_shadow_v2", "t.race_date", ""),
)


def one(sql: str):
    rows = fetch_all(sql)
    return dict(rows[0]) if rows else {}


def main() -> None:
    print("STORAGE_CURRENT_GROWTH_MODE=READ_ONLY_NO_MUTATION")
    measured = []
    for table, date_expr, join_sql in TABLES:
        row = one(
            f"""
            select count(*)::bigint as rows,
                   count(distinct {date_expr})::bigint as active_dates,
                   min({date_expr}) as min_date,
                   max({date_expr}) as max_date,
                   coalesce(sum(pg_column_size(t)),0)::bigint as logical_bytes,
                   pg_total_relation_size('public.{table}'::regclass)::bigint as relation_bytes
              from public.{table} t
              {join_sql}
             where {date_expr} >= current_date - 7
               and {date_expr} < current_date
            """
        )
        rows = int(row.get("rows") or 0)
        logical = int(row.get("logical_bytes") or 0)
        relation = int(row.get("relation_bytes") or 0)
        measured.append((logical, table, rows, relation, row))

    measured.sort(reverse=True)
    for logical, table, rows, relation, row in measured:
        print(
            "STORAGE_CURRENT_GROWTH_TABLE="
            f"name:{table} rows7:{rows} active_dates:{int(row.get('active_dates') or 0)} "
            f"min_date:{row.get('min_date')} max_date:{row.get('max_date')} "
            f"logical_bytes7:{logical} avg_logical_bytes_per_calendar_day:{logical/7.0:.2f} "
            f"avg_rows_per_calendar_day:{rows/7.0:.2f} relation_bytes:{relation}"
        )

    total_logical = sum(x[0] for x in measured)
    total_rows = sum(x[2] for x in measured)
    print(
        "STORAGE_CURRENT_GROWTH_TOTAL="
        f"rows7:{total_rows} logical_bytes7:{total_logical} "
        f"avg_logical_bytes_per_calendar_day:{total_logical/7.0:.2f}"
    )
    print("STORAGE_CURRENT_GROWTH_INTERPRETATION=LOGICAL_COMPARISON_NOT_PHYSICAL_RECLAIM")
    print("STORAGE_CURRENT_GROWTH_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
