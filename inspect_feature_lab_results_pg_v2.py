# -*- coding: utf-8 -*-
"""
inspect_feature_lab_results_pg_v2.py

Feature Lab保存結果と前走STスナップショットを、
DBドライバの行型に依存せず明示列で表示する読み取り専用監査。

Railway Start Command:
    python -u inspect_feature_lab_results_pg_v2.py
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from db_pg import fetch_all, fetch_one

START = os.getenv("DIAG_START_DATE") or "2026-01-01"
END = os.getenv("DIAG_END_DATE") or "2026-03-31"


def as_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return {"value": row}


def j(row: Any) -> str:
    return json.dumps(as_dict(row), ensure_ascii=False, default=str)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ inspect_feature_lab_results_pg_v2.py VERSION 2026-07-20 explicit-output-v2", flush=True)
    print(f"PERIOD={START}..{END}", flush=True)
    print("読み取り専用です。", flush=True)

    print("\n=== FEATURE LAB RESULTS ===", flush=True)
    rows = fetch_all(
        """select
             id, period_start, period_end, snapshot_label, selector_mode,
             config_name, evaluated_races, avg_result_prob_rank,
             top3_rate, top5_rate, top10_rate, top20_rate,
             improved_races, worsened_races, same_races,
             previous_st_coverage_races, racer_course_full_coverage_races,
             baseline_avg_delta, baseline_top5_delta, baseline_top10_delta,
             score, config, updated_at
           from v2_feature_lab_results
           where period_start <= %s and period_end >= %s
           order by period_start, period_end, config_name, updated_at;""",
        (END, START),
    )
    print(f"rows={len(rows)}", flush=True)
    for idx, row in enumerate(rows, 1):
        d = as_dict(row)
        print(
            f"[{idx}] config_name={d.get('config_name')} "
            f"period={d.get('period_start')}..{d.get('period_end')} "
            f"label={d.get('snapshot_label')} selector={d.get('selector_mode')} "
            f"races={d.get('evaluated_races')} avg_rank={d.get('avg_result_prob_rank')} "
            f"top5={d.get('top5_rate')} top10={d.get('top10_rate')} top20={d.get('top20_rate')} "
            f"improved={d.get('improved_races')} worsened={d.get('worsened_races')} "
            f"same={d.get('same_races')} prev_st_races={d.get('previous_st_coverage_races')} "
            f"baseline_avg_delta={d.get('baseline_avg_delta')} "
            f"baseline_top5_delta={d.get('baseline_top5_delta')} "
            f"baseline_top10_delta={d.get('baseline_top10_delta')} "
            f"score={d.get('score')} updated_at={d.get('updated_at')}",
            flush=True,
        )
        print(f"    config={json.dumps(d.get('config'), ensure_ascii=False, default=str)}", flush=True)

    print("\n=== PREVIOUS ST COVERAGE BY SNAPSHOT LABEL ===", flush=True)
    rows = fetch_all(
        """select
             coalesce(s.snapshot_label, '(null)') snapshot_label,
             count(*) rows,
             count(*) filter (where s.previous_st is not null) previous_st_nonnull,
             count(distinct s.race_id) races,
             count(distinct s.race_id) filter (where s.previous_st is not null) previous_st_races,
             min(s.previous_st) min_st,
             max(s.previous_st) max_st,
             avg(s.previous_st) avg_st
           from v2_realtime_racer_condition_snapshots s
           join v2_races r on r.race_id=s.race_id
           where r.race_date between %s and %s
           group by coalesce(s.snapshot_label, '(null)')
           order by snapshot_label;""",
        (START, END),
    )
    print(f"groups={len(rows)}", flush=True)
    for row in rows:
        print(j(row), flush=True)

    print("\n=== PREVIOUS ST COVERAGE BY LANE ===", flush=True)
    rows = fetch_all(
        """select
             s.lane,
             count(*) rows,
             count(s.previous_st) previous_st_nonnull,
             count(distinct s.race_id) filter (where s.previous_st is not null) previous_st_races,
             avg(s.previous_st) avg_st
           from v2_realtime_racer_condition_snapshots s
           join v2_races r on r.race_id=s.race_id
           where r.race_date between %s and %s
           group by s.lane
           order by s.lane;""",
        (START, END),
    )
    print(f"lanes={len(rows)}", flush=True)
    for row in rows:
        print(j(row), flush=True)

    print("\n=== PREVIOUS ST DISTRIBUTION ===", flush=True)
    row = fetch_one(
        """select
             count(s.previous_st) n,
             count(*) filter (where s.previous_st = 0) zero_n,
             count(*) filter (where s.previous_st > 0 and s.previous_st <= 0.08) le_008,
             count(*) filter (where s.previous_st > 0.08 and s.previous_st <= 0.12) b_009_012,
             count(*) filter (where s.previous_st > 0.12 and s.previous_st <= 0.17) b_013_017,
             count(*) filter (where s.previous_st > 0.17 and s.previous_st <= 0.22) b_018_022,
             count(*) filter (where s.previous_st > 0.22 and s.previous_st <= 0.30) b_023_030,
             count(*) filter (where s.previous_st > 0.30) gt_030
           from v2_realtime_racer_condition_snapshots s
           join v2_races r on r.race_id=s.race_id
           where r.race_date between %s and %s;""",
        (START, END),
    )
    print(j(row), flush=True)

    print("\n=== DUPLICATE SNAPSHOTS PER RACE/LANE ===", flush=True)
    row = fetch_one(
        """select count(*) duplicated_keys, coalesce(max(n), 0) max_snapshots_per_key
           from (
             select s.race_id, s.lane, count(*) n
             from v2_realtime_racer_condition_snapshots s
             join v2_races r on r.race_id=s.race_id
             where r.race_date between %s and %s
             group by s.race_id, s.lane
             having count(*) > 1
           ) x;""",
        (START, END),
    )
    print(j(row), flush=True)

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
    )
    print(j(row), flush=True)

    print("\n=== SAMPLE PREVIOUS ST ROWS ===", flush=True)
    rows = fetch_all(
        """select
             r.race_date, s.race_id, s.snapshot_label, s.lane, s.racer_number,
             s.previous_race_no, s.previous_course, s.previous_st, s.previous_finish,
             s.snapshot_at, s.source
           from v2_realtime_racer_condition_snapshots s
           join v2_races r on r.race_id=s.race_id
           where r.race_date between %s and %s
             and s.previous_st is not null
           order by r.race_date, s.race_id, s.lane
           limit 12;""",
        (START, END),
    )
    for row in rows:
        print(j(row), flush=True)

    print("\n=== finished ===", flush=True)


if __name__ == "__main__":
    main()