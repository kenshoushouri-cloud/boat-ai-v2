# -*- coding: utf-8 -*-
"""Read-only temporal robustness check for meet-day / race-number upset patterns.

This is confirmatory only, not an independent holdout. It uses a 7-day inference
buffer before the evaluation start so a meet already in progress on 2025-07-01
is not falsely labeled as day 1.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row

import upset_by_meet_day_race_no as base

DB = os.getenv("DATABASE_URL", "").strip()
START = date(2025, 7, 1)
END = date(2026, 8, 24)
BUFFER_DAYS = 7
BLOCKS = (
    ("B1_2025JUL_OCT", date(2025, 7, 1), date(2025, 10, 31)),
    ("B2_2025NOV_2026FEB", date(2025, 11, 1), date(2026, 2, 28)),
    ("B3_2026MAR_MAY", date(2026, 3, 1), date(2026, 5, 31)),
    ("B4_2026JUN_AUG24", date(2026, 6, 1), date(2026, 8, 24)),
)


def race_group(rno: int) -> str:
    if 2 <= rno <= 4:
        return "R02_04"
    if 7 <= rno <= 8:
        return "R07_08"
    if 11 <= rno <= 12:
        return "R11_12"
    return "OTHER"


def emit(label: str, rows: list[dict[str, Any]], baseline: float) -> dict[str, Any]:
    m = base.summarize(rows)
    base.emit(label, m, baseline)
    return m


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("UPSET_STABILITY_MODE=read_only_temporal_robustness_no_tuning", flush=True)
    print(f"UPSET_STABILITY_PERIOD={START}..{END} inference_buffer_days:{BUFFER_DAYS}", flush=True)
    print("UPSET_STABILITY_PRIMARY=trifecta_payout_yen>=10000", flush=True)
    print("UPSET_STABILITY_BLOCKS=B1_2025JUL_OCT,B2_2025NOV_2026FEB,B3_2026MAR_MAY,B4_2026JUN_AUG24", flush=True)
    print("UPSET_STABILITY_POLICY=confirmatory_same_history_not_independent_holdout_no_rule_selection_no_writes_no_production_no_line", flush=True)

    query_start = START - timedelta(days=BUFFER_DAYS)
    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select q.race_id,q.race_date::date race_date,
                       lpad(coalesce(nullif(q.venue_id::text,''),nullif(q.venue_code::text,'')),2,'0') venue,
                       q.race_no::int race_no,
                       r.first_lane::int first_lane,
                       r.trifecta_payout_yen::float8 payout
                from v2_results r
                join v2_races q on q.race_id=r.race_id
                where q.race_date between %s and %s
                  and q.race_no between 1 and 12
                  and r.first_lane between 1 and 6
                  and r.trifecta_payout_yen is not null
                  and r.trifecta_payout_yen > 0
                  and coalesce(r.result_status,'')='official'
                  and coalesce(r.race_status,'')='official'
                order by venue,race_date,race_no
                """,
                (query_start, END),
            )
            raw = [dict(r) for r in cur.fetchall()]

    venue_dates: dict[str, list[date]] = defaultdict(list)
    for r in raw:
        venue_dates[str(r["venue"])].append(r["race_date"])
    venue_dates = {v: sorted(set(ds)) for v, ds in venue_dates.items()}

    day_map: dict[tuple[str, date], int] = {}
    ambiguous: set[tuple[str, date]] = set()
    ambiguous_streaks = 0
    for venue, dates in venue_dates.items():
        streak: list[date] = []
        streaks: list[list[date]] = []
        for d in dates:
            if not streak or d == streak[-1] + timedelta(days=1):
                streak.append(d)
            else:
                streaks.append(streak)
                streak = [d]
        if streak:
            streaks.append(streak)
        for s in streaks:
            if len(s) > base.MAX_MEET_DAYS:
                ambiguous_streaks += 1
                ambiguous.update((venue, d) for d in s)
            else:
                for i, d in enumerate(s, 1):
                    day_map[(venue, d)] = i

    rows: list[dict[str, Any]] = []
    excluded = 0
    for r in raw:
        if not (START <= r["race_date"] <= END):
            continue
        key = (str(r["venue"]), r["race_date"])
        if key in ambiguous or key not in day_map:
            excluded += 1
            continue
        x = dict(r)
        x["meet_day"] = day_map[key]
        x["day_bucket"] = base.day_bucket(x["meet_day"])
        x["race_band"] = base.race_band(int(x["race_no"]))
        x["race_group"] = race_group(int(x["race_no"]))
        rows.append(x)

    print(f"UPSET_STABILITY_COVERAGE=evaluated:{len(rows)} excluded:{excluded} ambiguous_streaks:{ambiguous_streaks}", flush=True)

    d1_positive = 0
    r0204_positive = 0
    d1_lane1loss_positive = 0
    for name, lo, hi in BLOCKS:
        br = [r for r in rows if lo <= r["race_date"] <= hi]
        allm = base.summarize(br)
        baseline = float(allm.get("manshu_rate", 0.0))
        print(f"UPSET_STABILITY_BLOCK={name} start:{lo} end:{hi} n:{len(br)} baseline_manshu:{baseline*100:.2f}%", flush=True)
        d1 = emit(f"STAB:{name}:D1", [r for r in br if r["meet_day"] == 1], baseline)
        d2 = emit(f"STAB:{name}:D2", [r for r in br if r["meet_day"] == 2], baseline)
        emit(f"STAB:{name}:D3_4", [r for r in br if r["meet_day"] in (3, 4)], baseline)
        emit(f"STAB:{name}:D5_PLUS", [r for r in br if r["meet_day"] >= 5], baseline)
        r0204 = emit(f"STAB:{name}:R02_04", [r for r in br if r["race_group"] == "R02_04"], baseline)
        emit(f"STAB:{name}:R07_08", [r for r in br if r["race_group"] == "R07_08"], baseline)
        emit(f"STAB:{name}:R11_12", [r for r in br if r["race_group"] == "R11_12"], baseline)
        for rb in ("R01_04", "R05_08", "R09_12"):
            emit(f"STAB:{name}:D1_{rb}", [r for r in br if r["meet_day"] == 1 and r["race_band"] == rb], baseline)
        if d1.get("manshu_rate", 0.0) > baseline:
            d1_positive += 1
        if r0204.get("manshu_rate", 0.0) > baseline:
            r0204_positive += 1
        if d1.get("lane1_loss", 0.0) > allm.get("lane1_loss", 0.0):
            d1_lane1loss_positive += 1
        print(
            f"UPSET_STABILITY_COMPARE={name} D1_minus_all_manshu:{(d1.get('manshu_rate',0)-baseline)*100:+.2f}pt "
            f"D2_minus_all_manshu:{(d2.get('manshu_rate',0)-baseline)*100:+.2f}pt "
            f"R02_04_minus_all_manshu:{(r0204.get('manshu_rate',0)-baseline)*100:+.2f}pt",
            flush=True,
        )

    print(
        f"UPSET_STABILITY_SIGN_COUNTS=D1_manshu_above_all:{d1_positive}/4 "
        f"D1_lane1loss_above_all:{d1_lane1loss_positive}/4 R02_04_manshu_above_all:{r0204_positive}/4",
        flush=True,
    )
    print("UPSET_STABILITY_INTERPRETATION=TEMPORAL_ROBUSTNESS_ONLY_NOT_INDEPENDENT_VALIDATION", flush=True)
    print("UPSET_STABILITY_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("UPSET_STABILITY_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"UPSET_STABILITY_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
