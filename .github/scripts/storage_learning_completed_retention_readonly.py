# -*- coding: utf-8 -*-
"""Read-only retention inventory for completed learning_all realtime rows.

This does not claim that completed learning rows are disposable. It separates the
live Production dependency (same-race previous-odds semantics while a race is active)
from post-race research/reproducibility value. No mutation is performed.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


TABLES = (
    ("v2_realtime_odds_snapshots", ("race_id", "ticket")),
    ("v2_realtime_weather_snapshots", ("race_id",)),
    ("v2_realtime_exhibition_snapshots", ("race_id", "lane")),
    ("v2_realtime_entry_snapshots", ("race_id", "lane")),
    ("v2_realtime_race_condition_snapshots", ("race_id",)),
    ("v2_realtime_racer_condition_snapshots", ("race_id", "lane")),
)


def one(sql: str):
    rows = fetch_all(sql)
    return dict(rows[0]) if rows else {}


def main() -> None:
    print("STORAGE_LEARNING_COMPLETED_MODE=READ_ONLY_NO_MUTATION")
    total_rows = total_bytes = total_overlap = total_recent_bytes = 0

    for table, keys in TABLES:
        join = " and ".join(f"f.{k}=l.{k}" for k in keys)
        row = one(
            f"""
            select count(*)::bigint as learning_rows,
                   count(distinct l.race_id)::bigint as learning_races,
                   coalesce(sum(pg_column_size(l)),0)::bigint as learning_logical_bytes,
                   count(*) filter (where f.race_id is not null)::bigint as final_overlap_rows,
                   count(*) filter (where f.race_id is null)::bigint as learning_only_rows,
                   count(*) filter (where f.race_id is not null and f.snapshot_at >= l.snapshot_at)::bigint as final_at_or_after_learning,
                   count(*) filter (where f.race_id is not null and l.snapshot_at > f.snapshot_at)::bigint as learning_after_final,
                   count(*) filter (where l.race_date >= current_date-7)::bigint as recent7_rows,
                   coalesce(sum(pg_column_size(l)) filter (where l.race_date >= current_date-7),0)::bigint as recent7_logical_bytes,
                   min(l.race_date) as min_date,
                   max(l.race_date) as max_date
              from public.{table} l
              left join public.{table} f
                on f.snapshot_label='final_ab' and {join}
             where l.snapshot_label='learning_all'
               and l.race_date < current_date
            """
        )
        learning_rows = int(row.get("learning_rows") or 0)
        logical = int(row.get("learning_logical_bytes") or 0)
        overlap = int(row.get("final_overlap_rows") or 0)
        recent_bytes = int(row.get("recent7_logical_bytes") or 0)
        total_rows += learning_rows
        total_bytes += logical
        total_overlap += overlap
        total_recent_bytes += recent_bytes
        print(
            "STORAGE_LEARNING_COMPLETED_TABLE="
            f"name:{table} rows:{learning_rows} races:{int(row.get('learning_races') or 0)} "
            f"logical_bytes:{logical} final_overlap_rows:{overlap} "
            f"learning_only_rows:{int(row.get('learning_only_rows') or 0)} "
            f"final_at_or_after_learning:{int(row.get('final_at_or_after_learning') or 0)} "
            f"learning_after_final:{int(row.get('learning_after_final') or 0)} "
            f"recent7_rows:{int(row.get('recent7_rows') or 0)} recent7_logical_bytes:{recent_bytes} "
            f"min_date:{row.get('min_date')} max_date:{row.get('max_date')}"
        )

    print(
        "STORAGE_LEARNING_COMPLETED_TOTAL="
        f"rows:{total_rows} logical_bytes:{total_bytes} final_overlap_rows:{total_overlap} "
        f"recent7_logical_bytes:{total_recent_bytes} "
        f"avg_recent7_logical_bytes_per_calendar_day:{total_recent_bytes/7.0:.2f}"
    )
    print("STORAGE_LEARNING_COMPLETED_GATE=LIVE_DEPENDENCY_ENDED_FOR_COMPLETED_RACE_IDS_RESEARCH_RETENTION_NOT_PROVEN_DISPOSABLE")
    print("STORAGE_LEARNING_COMPLETED_RESULT=PASS_READ_ONLY")


if __name__ == '__main__':
    main()
