# -*- coding: utf-8 -*-
"""Read-only readiness audit for official racer-by-course daily snapshots.

This audit intentionally creates no predictive coefficient. It only checks whether
`v2_racer_course_stats_snapshots` is dense and chronologically safe enough for a
later fixed incremental OOS test over current v24.

Important interpretation:
- the official table is course-specific, while an early PRE race card only knows
  the frame/lane. This audit therefore measures the conservative lane-as-course
  proxy that would be available before exhibition/course changes are known.
- snapshot rows must have been created before each race deadline.
- no result/outcome data are read here, so readiness cannot be selected from
  apparent predictive performance.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from typing import Any

import psycopg
from psycopg.rows import dict_row

DB = os.getenv("DATABASE_URL", "").strip()
MIN_DATES = 20
MIN_FULL6_RACES = 2000
MIN_TIMING_SAFE_PCT = 99.5
MIN_FIELD_COMPLETE_PCT = 95.0


def sf(v: Any) -> float | None:
    try:
        if v in (None, ""):
            return None
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def corr(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    xs = [x for x, _ in pairs]
    ys = [y for _, y in pairs]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in pairs) / math.sqrt(vx * vy)


def pct(n: int, d: int) -> float:
    return 100.0 * n / d if d else 0.0


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")

    print("RACER_COURSE_READY_MODE=read_only_no_results_no_coefficients", flush=True)
    print("RACER_COURSE_READY_PROXY=early_pre_lane_as_course", flush=True)
    print("RACER_COURSE_READY_POLICY=no_writes_no_production_no_line_no_threshold_tuning", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='180s'")
            cur.execute(
                """
                select min(snapshot_date) min_date,
                       max(snapshot_date) max_date,
                       count(distinct snapshot_date) snapshot_dates,
                       count(*) rows,
                       count(distinct racer_number) racers,
                       count(*) filter(where course between 1 and 6) valid_course_rows,
                       count(*) filter(where top3_rate between 0 and 100) valid_top3_rows,
                       count(*) filter(where avg_st between 0 and 1) valid_avg_st_rows,
                       count(*) filter(where entry_rate between 0 and 100) valid_entry_rate_rows
                  from v2_racer_course_stats_snapshots
                """
            )
            meta = dict(cur.fetchone() or {})
            if not meta.get("min_date") or not meta.get("max_date"):
                print("RACER_COURSE_READY_COVERAGE=empty", flush=True)
                print("RACER_COURSE_READY_VERDICT=INSUFFICIENT_NO_SNAPSHOTS", flush=True)
                print("RACER_COURSE_READY_RESULT=PASS_READ_ONLY", flush=True)
                return

            cur.execute(
                """
                with snap_dates as (
                  select distinct snapshot_date race_date
                    from v2_racer_course_stats_snapshots
                ),
                target_races as (
                  select r.race_id,r.race_date,r.deadline_at
                    from v2_races r join snap_dates d on d.race_date=r.race_date
                ),
                matched as (
                  select r.race_id,r.race_date,r.deadline_at,
                         e.lane,e.racer_number,
                         e.local_place2_rate,e.national_place2_rate,e.avg_st entry_avg_st,
                         s.entry_rate course_entry_rate,
                         s.top3_rate course_top3_rate,
                         s.avg_st course_avg_st,
                         s.created_at snapshot_created_at
                    from target_races r
                    join v2_race_entries e on e.race_id=r.race_id
                    left join v2_racer_course_stats_snapshots s
                      on s.racer_number=e.racer_number
                     and s.snapshot_date=r.race_date
                     and s.course=e.lane
                )
                select * from matched order by race_date,race_id,lane
                """
            )
            rows = [dict(x) for x in cur.fetchall()]

    by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_date: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    matched_entries = 0
    top3_valid = 0
    avg_st_valid = 0
    entry_rate_valid = 0
    timing_comparable = 0
    timing_safe = 0
    timing_unsafe = 0
    corr_top3_local: list[tuple[float, float]] = []
    corr_top3_national: list[tuple[float, float]] = []
    corr_course_entry_avgst: list[tuple[float, float]] = []

    for row in rows:
        rid = str(row["race_id"])
        by_race[rid].append(row)
        d = str(row["race_date"])
        by_date[d]["entries"] += 1

        ctop3 = sf(row.get("course_top3_rate"))
        cst = sf(row.get("course_avg_st"))
        centry = sf(row.get("course_entry_rate"))
        if any(v is not None for v in (ctop3, cst, centry)):
            matched_entries += 1
            by_date[d]["matched"] += 1
        if ctop3 is not None and 0 <= ctop3 <= 100:
            top3_valid += 1
        if cst is not None and 0 <= cst <= 1:
            avg_st_valid += 1
        if centry is not None and 0 <= centry <= 100:
            entry_rate_valid += 1

        created = row.get("snapshot_created_at")
        deadline = row.get("deadline_at")
        if created is not None and deadline is not None:
            timing_comparable += 1
            if created < deadline:
                timing_safe += 1
            else:
                timing_unsafe += 1

        local = sf(row.get("local_place2_rate"))
        nat = sf(row.get("national_place2_rate"))
        east = sf(row.get("entry_avg_st"))
        if ctop3 is not None and local is not None:
            corr_top3_local.append((ctop3, local))
        if ctop3 is not None and nat is not None:
            corr_top3_national.append((ctop3, nat))
        if cst is not None and east is not None:
            corr_course_entry_avgst.append((cst, east))

    total_races = len(by_race)
    full6_races = 0
    full6_top3 = 0
    full6_avgst = 0
    full6_all3 = 0
    for race_rows in by_race.values():
        if len(race_rows) != 6:
            continue
        lanes = sorted(int(x.get("lane") or 0) for x in race_rows)
        if lanes != [1, 2, 3, 4, 5, 6]:
            continue
        matched6 = all(sf(x.get("course_top3_rate")) is not None or sf(x.get("course_avg_st")) is not None or sf(x.get("course_entry_rate")) is not None for x in race_rows)
        if matched6:
            full6_races += 1
        if all(sf(x.get("course_top3_rate")) is not None for x in race_rows):
            full6_top3 += 1
        if all(sf(x.get("course_avg_st")) is not None for x in race_rows):
            full6_avgst += 1
        if all(
            sf(x.get("course_top3_rate")) is not None
            and sf(x.get("course_avg_st")) is not None
            and sf(x.get("course_entry_rate")) is not None
            for x in race_rows
        ):
            full6_all3 += 1

    print(
        "RACER_COURSE_READY_META="
        f"min_date:{meta['min_date']} max_date:{meta['max_date']} "
        f"snapshot_dates:{meta['snapshot_dates']} rows:{meta['rows']} racers:{meta['racers']}",
        flush=True,
    )
    print(
        "RACER_COURSE_READY_RACES="
        f"target:{total_races} full6_any:{full6_races} full6_top3:{full6_top3} "
        f"full6_avgst:{full6_avgst} full6_all3:{full6_all3}",
        flush=True,
    )
    print(
        "RACER_COURSE_READY_ENTRIES="
        f"rows:{len(rows)} matched:{matched_entries} top3_valid:{top3_valid} "
        f"avgst_valid:{avg_st_valid} entry_rate_valid:{entry_rate_valid}",
        flush=True,
    )
    print(
        "RACER_COURSE_READY_TIMING="
        f"comparable:{timing_comparable} safe_before_deadline:{timing_safe} unsafe:{timing_unsafe} "
        f"safe_pct:{pct(timing_safe,timing_comparable):.2f}",
        flush=True,
    )

    def fmtcorr(v: float | None) -> str:
        return "NA" if v is None else f"{v:+.4f}"

    print(
        "RACER_COURSE_READY_REDUNDANCY="
        f"corr_course_top3_vs_local_place2:{fmtcorr(corr(corr_top3_local))} "
        f"corr_course_top3_vs_national_place2:{fmtcorr(corr(corr_top3_national))} "
        f"corr_course_avgst_vs_entry_avgst:{fmtcorr(corr(corr_course_entry_avgst))}",
        flush=True,
    )

    for d in sorted(by_date):
        m = by_date[d]
        print(
            f"RACER_COURSE_READY_DATE=date:{d} entries:{m['entries']} matched:{m['matched']} "
            f"matched_pct:{pct(m['matched'],m['entries']):.2f}",
            flush=True,
        )

    snapshot_dates = int(meta.get("snapshot_dates") or 0)
    timing_pct = pct(timing_safe, timing_comparable)
    top3_pct = pct(full6_top3, total_races)
    avgst_pct = pct(full6_avgst, total_races)
    ready = (
        snapshot_dates >= MIN_DATES
        and full6_races >= MIN_FULL6_RACES
        and timing_comparable > 0
        and timing_pct >= MIN_TIMING_SAFE_PCT
        and top3_pct >= MIN_FIELD_COMPLETE_PCT
        and avgst_pct >= MIN_FIELD_COMPLETE_PCT
    )
    print(
        "RACER_COURSE_READY_GATE="
        f"min_dates:{MIN_DATES} actual_dates:{snapshot_dates} "
        f"min_full6:{MIN_FULL6_RACES} actual_full6:{full6_races} "
        f"timing_safe_pct:{timing_pct:.2f}/{MIN_TIMING_SAFE_PCT:.2f} "
        f"full6_top3_pct:{top3_pct:.2f}/{MIN_FIELD_COMPLETE_PCT:.2f} "
        f"full6_avgst_pct:{avgst_pct:.2f}/{MIN_FIELD_COMPLETE_PCT:.2f}",
        flush=True,
    )
    print(
        "RACER_COURSE_READY_VERDICT=" + ("READY_FOR_FIXED_INCREMENTAL_OOS" if ready else "INSUFFICIENT_FOR_INCREMENTAL_OOS"),
        flush=True,
    )
    print("RACER_COURSE_READY_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
