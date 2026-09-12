# -*- coding: utf-8 -*-
"""Read-only growth/coverage audit for the learning_all realtime label.

Capacity research only. Uses SELECT/catalog-safe expressions through fetch_all.
It estimates logical tuple growth, not physical Railway volume reclaim.
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


def rows(sql: str):
    return [dict(r) for r in fetch_all(sql)]


def one(sql: str):
    data = rows(sql)
    return data[0] if data else {}


def _ident_list(columns: tuple[str, ...]) -> str:
    return ",".join(columns)


def _join_pred(columns: tuple[str, ...]) -> str:
    return " and ".join(f"f.{c}=l.{c}" for c in columns)


def main() -> None:
    print("STORAGE_LEARNING_ALL_GROWTH_MODE=READ_ONLY_NO_MUTATION")

    aggregate_learning_rows = 0
    aggregate_learning_logical_bytes = 0
    aggregate_recent_learning_rows = 0
    aggregate_recent_learning_logical_bytes = 0
    aggregate_recent_final_rows = 0
    aggregate_learning_only = 0
    aggregate_recent_learning_only = 0

    for table, identity_columns in TABLES:
        labels = rows(
            f"""
            select snapshot_label,
                   count(*)::bigint as row_count,
                   coalesce(sum(pg_column_size(t)),0)::bigint as logical_row_bytes,
                   count(distinct race_id)::bigint as race_count,
                   min(race_date) as min_date,
                   max(race_date) as max_date
              from {table} t
             where snapshot_label in ('final_ab','learning_all')
             group by snapshot_label
             order by snapshot_label
            """
        )
        by_label = {str(r.get("snapshot_label")): r for r in labels}
        learning = by_label.get("learning_all", {})
        final = by_label.get("final_ab", {})

        recent = rows(
            f"""
            select snapshot_label,
                   count(*)::bigint as row_count,
                   coalesce(sum(pg_column_size(t)),0)::bigint as logical_row_bytes,
                   count(distinct race_id)::bigint as race_count
              from {table} t
             where snapshot_label in ('final_ab','learning_all')
               and race_date >= current_date - 7
               and race_date < current_date
             group by snapshot_label
             order by snapshot_label
            """
        )
        recent_by_label = {str(r.get("snapshot_label")): r for r in recent}
        recent_learning = recent_by_label.get("learning_all", {})
        recent_final = recent_by_label.get("final_ab", {})

        join_pred = _join_pred(identity_columns)
        first_identity = identity_columns[0]
        learning_only = one(
            f"""
            with f as (
              select {_ident_list(identity_columns)}
                from {table}
               where snapshot_label='final_ab'
            ), l as (
              select {_ident_list(identity_columns)},race_id,race_date
                from {table}
               where snapshot_label='learning_all'
            )
            select count(*)::bigint as row_count,
                   count(distinct l.race_id)::bigint as race_count,
                   min(l.race_date) as min_date,
                   max(l.race_date) as max_date,
                   count(*) filter (
                     where l.race_date >= current_date - 7
                       and l.race_date < current_date
                   )::bigint as recent_row_count
              from l left join f on {join_pred}
             where f.{first_identity} is null
            """
        )

        learning_rows = int(learning.get("row_count") or 0)
        learning_bytes = int(learning.get("logical_row_bytes") or 0)
        recent_learning_rows = int(recent_learning.get("row_count") or 0)
        recent_learning_bytes = int(recent_learning.get("logical_row_bytes") or 0)
        recent_final_rows = int(recent_final.get("row_count") or 0)
        learning_only_rows = int(learning_only.get("row_count") or 0)
        recent_learning_only_rows = int(learning_only.get("recent_row_count") or 0)

        aggregate_learning_rows += learning_rows
        aggregate_learning_logical_bytes += learning_bytes
        aggregate_recent_learning_rows += recent_learning_rows
        aggregate_recent_learning_logical_bytes += recent_learning_bytes
        aggregate_recent_final_rows += recent_final_rows
        aggregate_learning_only += learning_only_rows
        aggregate_recent_learning_only += recent_learning_only_rows

        print(
            "STORAGE_LEARNING_ALL_TABLE="
            f"name:{table} "
            f"final_rows:{int(final.get('row_count') or 0)} "
            f"learning_rows:{learning_rows} "
            f"learning_logical_bytes:{learning_bytes} "
            f"recent7_final_rows:{recent_final_rows} "
            f"recent7_learning_rows:{recent_learning_rows} "
            f"recent7_learning_logical_bytes:{recent_learning_bytes} "
            f"learning_only_rows:{learning_only_rows} "
            f"learning_only_races:{int(learning_only.get('race_count') or 0)} "
            f"recent7_learning_only_rows:{recent_learning_only_rows} "
            f"learning_only_min_date:{learning_only.get('min_date')} "
            f"learning_only_max_date:{learning_only.get('max_date')}"
        )

    avg_learning_rows_day = aggregate_recent_learning_rows / 7.0
    avg_learning_bytes_day = aggregate_recent_learning_logical_bytes / 7.0
    overlap_recent = max(0, aggregate_recent_learning_rows - aggregate_recent_learning_only)
    overlap_pct = (
        100.0 * overlap_recent / aggregate_recent_learning_rows
        if aggregate_recent_learning_rows
        else 0.0
    )

    print(
        "STORAGE_LEARNING_ALL_TOTAL="
        f"learning_rows:{aggregate_learning_rows} "
        f"learning_logical_bytes:{aggregate_learning_logical_bytes} "
        f"learning_only_rows:{aggregate_learning_only} "
        f"recent7_final_rows:{aggregate_recent_final_rows} "
        f"recent7_learning_rows:{aggregate_recent_learning_rows} "
        f"recent7_learning_logical_bytes:{aggregate_recent_learning_logical_bytes} "
        f"recent7_learning_only_rows:{aggregate_recent_learning_only} "
        f"recent7_identity_overlap_pct:{overlap_pct:.4f} "
        f"avg_learning_rows_per_completed_day:{avg_learning_rows_day:.2f} "
        f"avg_learning_logical_bytes_per_completed_day:{avg_learning_bytes_day:.2f}"
    )
    print("STORAGE_LEARNING_ALL_GROWTH_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
