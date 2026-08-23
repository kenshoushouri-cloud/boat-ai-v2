# -*- coding: utf-8 -*-
"""Contemporaneous read-only probe of official exhibition-data availability.

For races around the current time, fetch BOAT RACE official `beforeinfo`
directly and report whether six lanes and a complete exhibition-time rank
permutation are available at the observed minutes-before-deadline.

This is observation only. It never persists fetched data and never touches
Production decisions or LINE.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

import v21_realtime_collector_pg as rt

JST = timezone(timedelta(hours=9))
DB = os.getenv("DATABASE_URL", "").strip()
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
PAST_MIN = float(os.getenv("BAO_EXLIVE_PAST_MIN", "3"))
FUTURE_MIN = float(os.getenv("BAO_EXLIVE_FUTURE_MIN", "45"))
MAX_RACES = int(os.getenv("BAO_EXLIVE_MAX_RACES", "18"))
LANES = {1, 2, 3, 4, 5, 6}


def bucket(mb: float) -> str:
    if mb >= 30:
        return "m30_45"
    if mb >= 20:
        return "m20_30"
    if mb >= 15:
        return "m15_20"
    if mb >= 10:
        return "m10_15"
    if mb >= 5:
        return "m5_10"
    if mb >= 0:
        return "m0_5"
    return "after"


def inspect_beforeinfo(html: str | None):
    if not html:
        return {"state": "fetch_empty", "lanes": 0, "time_values": 0, "rank_ready": 0}
    if rt._looks_no_data(html):
        return {"state": "official_no_data", "lanes": 0, "time_values": 0, "rank_ready": 0}
    rows = rt.parse_exhibition(html)
    by = {}
    for row in rows:
        try:
            lane = int(row.get("lane") or 0)
        except Exception:
            lane = 0
        if lane in LANES:
            by[lane] = row
    times = 0
    ranks = []
    for lane in range(1, 7):
        row = by.get(lane, {})
        try:
            t = float(row.get("exhibition_time"))
            if t > 0:
                times += 1
        except Exception:
            pass
        try:
            r = int(float(row.get("exhibition_time_rank")))
            if r in LANES:
                ranks.append(r)
        except Exception:
            pass
    rank_ready = int(set(by) == LANES and len(ranks) == 6 and set(ranks) == LANES)
    state = "ready" if rank_ready else ("parsed_partial" if by else "parsed_zero")
    return {
        "state": state,
        "lanes": len(by),
        "time_values": times,
        "rank_ready": rank_ready,
    }


def main():
    if not DB:
        raise RuntimeError("DATABASE_URL is required")
    now = datetime.now(JST)
    print(
        f"BAO_EXLIVE_MODE=official_direct_read_only target:{TARGET_DATE} now:{now.isoformat()}",
        flush=True,
    )
    print(
        f"BAO_EXLIVE_WINDOW=past:{PAST_MIN:.1f} future:{FUTURE_MIN:.1f} max_races:{MAX_RACES}",
        flush=True,
    )
    print("BAO_EXLIVE_SOURCE=official_beforeinfo_no_db_snapshot_timestamps", flush=True)
    print("BAO_EXLIVE_POLICY=no_writes_no_production_no_line", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute(
                """select race_id,coalesce(venue_id,venue_code) venue_id,race_no,deadline_at
                   from v2_races
                   where race_date=%s and deadline_at is not null
                     and deadline_at >= %s and deadline_at <= %s
                   order by deadline_at
                   limit %s""",
                (
                    TARGET_DATE,
                    now - timedelta(minutes=PAST_MIN),
                    now + timedelta(minutes=FUTURE_MIN),
                    MAX_RACES,
                ),
            )
            races = [dict(x) for x in c.fetchall()]

    print(f"BAO_EXLIVE_TARGETS={len(races)}", flush=True)
    bins = defaultdict(lambda: {"n": 0, "ready": 0, "lanes6": 0, "time6": 0})
    ready_total = 0
    for r in races:
        deadline = r["deadline_at"]
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=JST)
        deadline = deadline.astimezone(JST)
        observed = datetime.now(JST)
        mb = (deadline - observed).total_seconds() / 60.0
        venue = str(r.get("venue_id") or "").zfill(2)
        rno = int(r.get("race_no") or 0)
        html = rt._fetch(rt._official_url("beforeinfo", TARGET_DATE, venue, rno))
        after_fetch = datetime.now(JST)
        mb2 = (deadline - after_fetch).total_seconds() / 60.0
        info = inspect_beforeinfo(html)
        b = bucket(mb2)
        bins[b]["n"] += 1
        bins[b]["ready"] += info["rank_ready"]
        bins[b]["lanes6"] += int(info["lanes"] == 6)
        bins[b]["time6"] += int(info["time_values"] == 6)
        ready_total += info["rank_ready"]
        print(
            f"BAO_EXLIVE_RACE=race:{r['race_id']} venue:{venue} rno:{rno} "
            f"mb:{mb2:.2f} bucket:{b} state:{info['state']} lanes:{info['lanes']} "
            f"time_values:{info['time_values']} rank_ready:{info['rank_ready']}",
            flush=True,
        )

    order = ("m30_45", "m20_30", "m15_20", "m10_15", "m5_10", "m0_5", "after")
    for b in order:
        s = bins[b]
        if s["n"]:
            print(
                f"BAO_EXLIVE_BIN={b} probed:{s['n']} lanes6:{s['lanes6']} "
                f"time6:{s['time6']} rank_ready:{s['ready']}",
                flush=True,
            )
    print(
        f"BAO_EXLIVE_SUMMARY=probed:{len(races)} rank_ready:{ready_total}",
        flush=True,
    )
    print("BAO_EXLIVE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
