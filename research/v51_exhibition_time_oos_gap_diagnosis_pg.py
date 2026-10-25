# -*- coding: utf-8 -*-
"""Read-only OOS Exhibition Time gap diagnosis for V5.1 research.

Period is frozen to 2026-07-01..2026-09-30.
No outcomes, odds, payouts, or DB writes are read/performed.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

START = date(2026, 7, 1)
END = date(2026, 9, 30)
LANES = {1, 2, 3, 4, 5, 6}
ACCEPTED_SOURCES = {
    "official_archived_beforeinfo_historical_reconstruction",
    "official_beforeinfo_historical",
    "official_beforeinfo_historical_v3_pilot",
}
CONTRACT = "V51_EXHIBITION_TIME_OOS_GAP_DIAG_V1"


def load(conn: psycopg.Connection[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select r.race_id,r.race_date,
                   count(e.*)::int as entry_rows,
                   count(distinct e.lane)::int as entry_lanes,
                   count(*) filter(
                     where e.lane between 1 and 6
                       and e.motor_place2_rate between 0 and 100
                   )::int as motor2_valid_entries
              from v2_races r
              left join v2_race_entries e on e.race_id=r.race_id
             where r.race_date between %s and %s
             group by r.race_id,r.race_date
             order by r.race_date,r.race_id
            """,
            (START, END),
        )
        races = [dict(x) for x in cur.fetchall()]

        cur.execute(
            """
            select race_id,race_date,lane,source,exhibition_time,
                   exhibition_time_rank,exhibition_time_diff
              from v2_realtime_exhibition_snapshots
             where race_date between %s and %s
               and snapshot_label='historical'
             order by race_date,race_id,lane
            """,
            (START, END),
        )
        ex = [dict(x) for x in cur.fetchall()]
    return races, ex


def summarize(races: list[dict[str, Any]], ex_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ex_rows:
        by_race[str(row["race_id"])].append(row)

    daily: dict[str, Counter[str]] = defaultdict(Counter)
    monthly: dict[str, Counter[str]] = defaultdict(Counter)
    source_month_rows: dict[str, Counter[str]] = defaultdict(Counter)
    source_month_races: dict[tuple[str, str], set[str]] = defaultdict(set)
    missing_dates: set[str] = set()

    for race in races:
        rid = str(race["race_id"])
        rd = race["race_date"]
        if isinstance(rd, str):
            rd = date.fromisoformat(rd)
        ds = rd.isoformat()
        month = ds[:7]

        rows = by_race.get(rid, [])
        accepted = [x for x in rows if str(x.get("source") or "") in ACCEPTED_SOURCES]
        lanes = {
            int(x.get("lane") or 0)
            for x in accepted
            if x.get("exhibition_time") is not None
        }
        time6 = lanes == LANES
        motor6 = (
            int(race["entry_rows"]) == 6
            and int(race["entry_lanes"]) == 6
            and int(race["motor2_valid_entries"]) == 6
        )

        for bucket in (daily[ds], monthly[month]):
            bucket["races"] += 1
            bucket["motor2_complete"] += int(motor6)
            bucket["time6"] += int(time6)
            bucket["shared_time6"] += int(motor6 and time6)
            bucket["missing_time6"] += int(not time6)

        if not time6:
            missing_dates.add(ds)

        seen_sources = set()
        for row in accepted:
            source = str(row.get("source") or "")
            source_month_rows[month][source] += 1
            seen_sources.add(source)
        for source in seen_sources:
            source_month_races[(month, source)].add(rid)

    daily_rows = []
    for ds in sorted(daily):
        c = daily[ds]
        daily_rows.append({
            "date": ds,
            **dict(c),
            "coverage_pct": round(100.0 * c["time6"] / c["races"], 4) if c["races"] else None,
        })

    monthly_rows = []
    for month in sorted(monthly):
        c = monthly[month]
        monthly_rows.append({
            "month": month,
            **dict(c),
            "coverage_pct": round(100.0 * c["time6"] / c["races"], 4) if c["races"] else None,
            "source_rows": dict(sorted(source_month_rows[month].items())),
            "source_races": {
                source: len(source_month_races[(month, source)])
                for source in sorted(source_month_rows[month])
            },
        })

    complete_dates = [x["date"] for x in daily_rows if x["missing_time6"] == 0]
    partial_dates = [x["date"] for x in daily_rows if x["time6"] > 0 and x["missing_time6"] > 0]
    zero_dates = [x["date"] for x in daily_rows if x["time6"] == 0]

    transitions = []
    prev_state = None
    for row in daily_rows:
        state = "COMPLETE" if row["missing_time6"] == 0 else ("ZERO" if row["time6"] == 0 else "PARTIAL")
        if state != prev_state:
            transitions.append({"date": row["date"], "state": state})
            prev_state = state

    gaps = []
    cur_start = None
    cur_end = None
    prev = None
    for ds in sorted(missing_dates):
        d = date.fromisoformat(ds)
        if cur_start is None:
            cur_start = cur_end = d
        elif prev is not None and d == prev + timedelta(days=1):
            cur_end = d
        else:
            gaps.append([cur_start.isoformat(), cur_end.isoformat()])
            cur_start = cur_end = d
        prev = d
    if cur_start is not None:
        gaps.append([cur_start.isoformat(), cur_end.isoformat()])

    totals = Counter()
    for row in daily_rows:
        totals["races"] += row["races"]
        totals["time6"] += row["time6"]
        totals["missing_time6"] += row["missing_time6"]

    return {
        "totals": {
            **dict(totals),
            "coverage_pct": round(100.0 * totals["time6"] / totals["races"], 4),
        },
        "monthly": monthly_rows,
        "daily": daily_rows,
        "date_classes": {
            "complete_days": len(complete_dates),
            "partial_days": len(partial_dates),
            "zero_days": len(zero_dates),
            "first_complete_day": complete_dates[0] if complete_dates else None,
            "last_complete_day": complete_dates[-1] if complete_dates else None,
            "first_partial_day": partial_dates[0] if partial_dates else None,
            "last_partial_day": partial_dates[-1] if partial_dates else None,
            "first_zero_day": zero_dates[0] if zero_dates else None,
            "last_zero_day": zero_dates[-1] if zero_dates else None,
            "zero_days": zero_dates,
        },
        "coverage_state_transitions": transitions,
        "missing_date_ranges": gaps,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V51_EX_TIME_OOS_GAP_CONTRACT={CONTRACT}", flush=True)
    print("V51_EX_TIME_OOS_GAP_RESULT_READ=0", flush=True)
    print("V51_EX_TIME_OOS_GAP_ODDS_READ=0", flush=True)
    print("V51_EX_TIME_OOS_GAP_PAYOUT_READ=0", flush=True)
    print("V51_EX_TIME_OOS_GAP_DB_WRITE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        races, ex = load(conn)
        conn.rollback()

    report = summarize(races, ex)
    payload = {
        "contract": CONTRACT,
        "period": [START.isoformat(), END.isoformat()],
        "accepted_sources": sorted(ACCEPTED_SOURCES),
        **report,
        "result_read": False,
        "odds_read": False,
        "payout_read": False,
        "database_write": False,
        "production_change": False,
    }
    Path("v51-exhibition-time-oos-gap-diagnosis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("V51_EX_TIME_OOS_GAP_TOTAL=" + json.dumps(payload["totals"], sort_keys=True), flush=True)
    for row in payload["monthly"]:
        print("V51_EX_TIME_OOS_GAP_MONTH=" + json.dumps(row, sort_keys=True), flush=True)
    print("V51_EX_TIME_OOS_GAP_DATE_CLASSES=" + json.dumps(payload["date_classes"], sort_keys=True), flush=True)
    print("V51_EX_TIME_OOS_GAP_TRANSITIONS=" + json.dumps(payload["coverage_state_transitions"], sort_keys=True), flush=True)
    print("V51_EX_TIME_OOS_GAP_RANGES=" + json.dumps(payload["missing_date_ranges"], sort_keys=True), flush=True)
    print("V51_EX_TIME_OOS_GAP_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
