# -*- coding: utf-8 -*-
"""
inspect_feature_lab_results_pg.py

v2_feature_lab_results と前走STスナップショットの保存状況を
読み取り専用で確認する最終監査。

Railway Start Command:
    python -u inspect_feature_lab_results_pg.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from db_pg import fetch_all, fetch_one

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime("%Y-%m-%d")
START = os.getenv("DIAG_START_DATE") or os.getenv("FEATURE_LAB_START_DATE") or "2026-01-01"
END = os.getenv("DIAG_END_DATE") or os.getenv("FEATURE_LAB_END_DATE") or "2026-03-31"


def pretty(v: Any, n: int = 4000) -> str:
    try:
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False, default=str)[:n]
        return str(v)[:n]
    except Exception:
        return repr(v)[:n]


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ inspect_feature_lab_results_pg.py VERSION 2026-07-20 final-source-audit-v1", flush=True)
    print(f"PERIOD={START}..{END}", flush=True)
    print("読み取り専用です。DB更新・LINE送信は行いません。", flush=True)

    print("\n=== FEATURE LAB RESULTS ===", flush=True)
    rows = fetch_all(
        """select *
           from v2_feature_lab_results
           where period_start <= %s and period_end >= %s
           order by period_start, period_end, config_name, updated_at;""",
        (END, START),
    )
    print(f"rows={len(rows)}", flush=True)
    for r in rows:
        print(pretty(r), flush=True)

    print("\n=== PREVIOUS ST COVERAGE BY SNAPSHOT LABEL ===", flush=True)
    rows = fetch_all(
        """select
             snapshot_label,
             count(*) rows,
             count(*) filter (where previous_st is not null) previous_st_nonnull,
             count(distinct race_id) races,
             count(distinct race_id) filter (where previous_st is not null) previous_st_races,
             min(previous_st) min_st,
             max(previous_st) max_st,
             avg(previous_st) avg_st
           from v2_realtime_racer_condition_snapshots
           where race_date between %s and %s
           group by snapshot_label
           order by snapshot_label;""",
        (START, END),
    )
    for r in rows:
        print(pretty(r), flush=True)

    print("\n=== PREVIOUS ST COVERAGE BY LANE ===", flush=True)
    rows = fetch_all(
        """select
             lane,
             count(*) rows,
             count(previous_st) previous_st_nonnull,
             count(distinct race_id) filter (where previous_st is not null) previous_st_races,
             avg(previous_st) avg_st
           from v2_realtime_racer_condition_snapshots
           where race_date between %s and %s
           group by lane
           order by lane;""",
        (START, END),
    )
    for r in rows:
        print(pretty(r), flush=True)

    print("\n=== PREVIOUS ST DISTRIBUTION ===", flush=True)
    row = fetch_one(
        """select
             count(previous_st) n,
             count(*) filter (where previous_st = 0) zero_n,
             count(*) filter (where previous_st > 0 and previous_st <= 0.08) le_008,
             count(*) filter (where previous_st > 0.08 and previous_st <= 0.12) b_009_012,
             count(*) filter (where previous_st > 0.12 and previous_st <= 0.17) b_013_017,
             count(*) filter (where previous_st > 0.17 and previous_st <= 0.22) b_018_022,
             count(*) filter (where previous_st > 0.22 and previous_st <= 0.30) b_023_030,
             count(*) filter (where previous_st > 0.30) gt_030
           from v2_realtime_racer_condition_snapshots
           where race_date between %s and %s;""",
        (START, END),
    ) or {}
    print(pretty(row), flush=True)

    print("\n=== DUPLICATE SNAPSHOTS PER RACE/LANE ===", flush=True)
    row = fetch_one(
        """select
             count(*) duplicated_keys,
             max(n) max_snapshots_per_key
           from (
             select race_id, lane, count(*) n
             from v2_realtime_racer_condition_snapshots
             where race_date between %s and %s
             group by race_id, lane
             having count(*) > 1
           ) x;""",
        (START, END),
    ) or {}
    print(pretty(row), flush=True)

    print("\n=== RESULT COMPLETENESS ===", flush=True)
    row = fetch_one(
        """select
             count(*) rows,
             count(*) filter (
               where first_lane is not null and second_lane is not null
                 and third_lane is not null and fourth_lane is not null
                 and fifth_lane is not null and sixth_lane is not null
             ) full_finish_rows,
             count(*) filter (
               where first_lane is not null and second_lane is not null
                 and third_lane is not null
             ) top3_rows
           from v2_results
           where race_date between %s and %s;""",
        (START, END),
    ) or {}
    print(pretty(row), flush=True)

    print("\n=== finished ===", flush=True)


if __name__ == "__main__":
    main()