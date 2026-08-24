# -*- coding: utf-8 -*-
"""Read-only venue-specific stability audit for upset rate by meet day and race band.

Goal: test whether the nationwide D1 / R02-04 patterns vary materially by venue.
No rule selection, tuning, DB writes, Production/LINE changes, or promotion.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row

DB = os.getenv("DATABASE_URL", "").strip()
START = date.fromisoformat("2025-07-01")
END = date.fromisoformat("2026-08-24")
BUFFER_DAYS = 7
MAX_MEET_DAYS = 7
MANSHU_YEN = 10_000
BLOCKS = [
    ("B1", date(2025, 7, 1), date(2025, 10, 31)),
    ("B2", date(2025, 11, 1), date(2026, 2, 28)),
    ("B3", date(2026, 3, 1), date(2026, 5, 31)),
    ("B4", date(2026, 6, 1), date(2026, 8, 24)),
]
VENUE_NAMES = {
    "01":"桐生","02":"戸田","03":"江戸川","04":"平和島","05":"多摩川","06":"浜名湖",
    "07":"蒲郡","08":"常滑","09":"津","10":"三国","11":"びわこ","12":"住之江",
    "13":"尼崎","14":"鳴門","15":"丸亀","16":"児島","17":"宮島","18":"徳山",
    "19":"下関","20":"若松","21":"芦屋","22":"福岡","23":"唐津","24":"大村",
}


def day_bucket(d: int) -> str:
    if d == 1: return "D1"
    if d == 2: return "D2"
    if d in (3, 4): return "D3_4"
    return "D5_PLUS"


def race_band(r: int) -> str:
    if 1 <= r <= 4: return "R01_04"
    if 5 <= r <= 8: return "R05_08"
    return "R09_12"


def rate(rows: list[dict[str, Any]]) -> float:
    return sum(float(x["payout"]) >= MANSHU_YEN for x in rows) / len(rows) if rows else 0.0


def lane1_loss(rows: list[dict[str, Any]]) -> float:
    return sum(int(x["first_lane"]) != 1 for x in rows) / len(rows) if rows else 0.0


def subset(rows, pred):
    return [x for x in rows if pred(x)]


def block_of(d: date) -> str | None:
    for name, s, e in BLOCKS:
        if s <= d <= e:
            return name
    return None


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("UPSET_VENUE_MODE=read_only_venue_meet_race_stability_no_tuning", flush=True)
    print(f"UPSET_VENUE_PERIOD={START}..{END} buffer_days:{BUFFER_DAYS}", flush=True)
    print("UPSET_VENUE_PRIMARY=trifecta_payout_yen>=10000", flush=True)
    print("UPSET_VENUE_POLICY=no_rule_selection_no_threshold_search_no_writes_no_production_no_line", flush=True)

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
                       q.race_no::int race_no,r.first_lane::int first_lane,
                       r.trifecta_payout_yen::float8 payout
                from v2_results r join v2_races q on q.race_id=r.race_id
                where q.race_date between %s and %s
                  and q.race_no between 1 and 12
                  and r.first_lane between 1 and 6
                  and r.trifecta_payout_yen is not null and r.trifecta_payout_yen>0
                  and coalesce(r.result_status,'')='official'
                  and coalesce(r.race_status,'')='official'
                order by venue,race_date,race_no
                """,
                (query_start, END),
            )
            raw = [dict(x) for x in cur.fetchall()]

    venue_dates: dict[str, list[date]] = defaultdict(list)
    for x in raw:
        venue_dates[str(x["venue"])].append(x["race_date"])
    venue_dates = {v: sorted(set(ds)) for v, ds in venue_dates.items()}

    day_map: dict[tuple[str, date], int] = {}
    ambiguous: set[tuple[str, date]] = set()
    ambiguous_streaks = 0
    for venue, dates in venue_dates.items():
        streaks: list[list[date]] = []
        cur: list[date] = []
        for d in dates:
            if not cur or d == cur[-1] + timedelta(days=1):
                cur.append(d)
            else:
                streaks.append(cur); cur = [d]
        if cur: streaks.append(cur)
        for st in streaks:
            if len(st) > MAX_MEET_DAYS:
                ambiguous_streaks += 1
                ambiguous.update((venue, d) for d in st)
                continue
            for i, d in enumerate(st, 1):
                day_map[(venue, d)] = i

    rows: list[dict[str, Any]] = []
    excluded = 0
    for x in raw:
        if not (START <= x["race_date"] <= END):
            continue
        key = (str(x["venue"]), x["race_date"])
        if key in ambiguous or key not in day_map:
            excluded += 1; continue
        y = dict(x)
        y["meet_day"] = day_map[key]
        y["day_bucket"] = day_bucket(y["meet_day"])
        y["race_band"] = race_band(int(y["race_no"]))
        y["block"] = block_of(y["race_date"])
        rows.append(y)

    print(f"UPSET_VENUE_COVERAGE=evaluated:{len(rows)} excluded:{excluded} ambiguous_streaks:{ambiguous_streaks}", flush=True)
    byv: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for x in rows: byv[str(x["venue"])].append(x)

    for venue in sorted(byv):
        rr = byv[venue]
        base = rate(rr)
        d1 = subset(rr, lambda x: x["meet_day"] == 1)
        d2 = subset(rr, lambda x: x["meet_day"] == 2)
        d34 = subset(rr, lambda x: x["day_bucket"] == "D3_4")
        d5p = subset(rr, lambda x: x["day_bucket"] == "D5_PLUS")
        r24 = subset(rr, lambda x: 2 <= int(x["race_no"]) <= 4)
        d1r14 = subset(rr, lambda x: x["meet_day"] == 1 and x["race_band"] == "R01_04")
        d1r58 = subset(rr, lambda x: x["meet_day"] == 1 and x["race_band"] == "R05_08")
        d1r912 = subset(rr, lambda x: x["meet_day"] == 1 and x["race_band"] == "R09_12")
        d1_sign = r24_sign = 0
        d1_block_deltas=[]; r24_block_deltas=[]
        for bn, _, _ in BLOCKS:
            br = subset(rr, lambda x, bn=bn: x["block"] == bn)
            if not br: continue
            bb=rate(br)
            bd1=subset(br, lambda x: x["meet_day"] == 1)
            br24=subset(br, lambda x: 2 <= int(x["race_no"]) <= 4)
            if bd1:
                delta=rate(bd1)-bb; d1_block_deltas.append(delta); d1_sign += int(delta>0)
            if br24:
                delta=rate(br24)-bb; r24_block_deltas.append(delta); r24_sign += int(delta>0)
        fmt=lambda xs: ",".join(f"{x*100:+.2f}" for x in xs)
        print(
            f"UPSET_VENUE=V{venue}:{VENUE_NAMES.get(venue,'?')} n:{len(rr)} base:{base*100:.2f}% "
            f"D1_n:{len(d1)} D1:{rate(d1)*100:.2f}% D1_delta:{(rate(d1)-base)*100:+.2f}pt D1_lane1loss:{lane1_loss(d1)*100:.2f}% D1_sign:{d1_sign}/{len(d1_block_deltas)} D1_block_delta:{fmt(d1_block_deltas)} "
            f"D2:{rate(d2)*100:.2f}% D34:{rate(d34)*100:.2f}% D5p:{rate(d5p)*100:.2f}% "
            f"R02_04_n:{len(r24)} R02_04:{rate(r24)*100:.2f}% R02_04_delta:{(rate(r24)-base)*100:+.2f}pt R02_04_sign:{r24_sign}/{len(r24_block_deltas)} R02_04_block_delta:{fmt(r24_block_deltas)} "
            f"D1_R01_04:{rate(d1r14)*100:.2f}%({len(d1r14)}) D1_R05_08:{rate(d1r58)*100:.2f}%({len(d1r58)}) D1_R09_12:{rate(d1r912)*100:.2f}%({len(d1r912)})",
            flush=True,
        )

    print("UPSET_VENUE_INTERPRETATION=VENUE_HETEROGENEITY_AUDIT_ONLY_REQUIRE_SHRINKAGE_AND_FORWARD_VALIDATION_BEFORE_MODEL_USE", flush=True)
    print("UPSET_VENUE_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("UPSET_VENUE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg=str(exc).replace("\n"," ").replace("\r"," ")[:700]
        print(f"UPSET_VENUE_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
