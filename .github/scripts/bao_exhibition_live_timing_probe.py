# -*- coding: utf-8 -*-
"""Contemporaneous read-only probe of official exhibition-data availability.

Fetch at most one BOAT RACE official `beforeinfo` page per minutes-before bucket.
This deliberately uses a small sequential request pattern because the official
site timed out under parallel probing from GitHub-hosted runners.

Observation only: no fetched data is persisted and no Production/LINE state is
touched.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import psycopg
import requests
from psycopg.rows import dict_row

import v21_realtime_collector_pg as rt

JST = timezone(timedelta(hours=9))
DB = os.getenv("DATABASE_URL", "").strip()
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
PAST_MIN = float(os.getenv("BAO_EXLIVE_PAST_MIN", "3"))
FUTURE_MIN = float(os.getenv("BAO_EXLIVE_FUTURE_MIN", "45"))
HTTP_TIMEOUT = float(os.getenv("BAO_EXLIVE_HTTP_TIMEOUT", "20"))
LANES = {1, 2, 3, 4, 5, 6}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2-exhibition-live-probe/1.0)"}
BUCKET_MIDPOINT = {
    "after": -1.5,
    "m0_5": 2.5,
    "m5_10": 7.5,
    "m10_15": 12.5,
    "m15_20": 17.5,
    "m20_30": 25.0,
    "m30_45": 37.5,
}
BUCKET_ORDER = ("m30_45", "m20_30", "m15_20", "m10_15", "m5_10", "m0_5", "after")


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
            rank = int(float(row.get("exhibition_time_rank")))
            if rank in LANES:
                ranks.append(rank)
        except Exception:
            pass
    rank_ready = int(set(by) == LANES and len(ranks) == 6 and set(ranks) == LANES)
    state = "ready" if rank_ready else ("parsed_partial" if by else "parsed_zero")
    return {"state": state, "lanes": len(by), "time_values": times, "rank_ready": rank_ready}


def select_one_per_bucket(races, now):
    best = {}
    for r in races:
        deadline = r["deadline_at"]
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=JST)
        deadline = deadline.astimezone(JST)
        mb = (deadline - now).total_seconds() / 60.0
        b = bucket(mb)
        midpoint = BUCKET_MIDPOINT[b]
        key = abs(mb - midpoint)
        if b not in best or key < best[b][0]:
            item = dict(r)
            item["deadline_at"] = deadline
            best[b] = (key, item)
    return [best[b][1] for b in BUCKET_ORDER if b in best]


def fetch_one(session, r):
    deadline = r["deadline_at"]
    venue = str(r.get("venue_id") or "").zfill(2)
    rno = int(r.get("race_no") or 0)
    url = rt._official_url("beforeinfo", TARGET_DATE, venue, rno)
    html = None
    transport_ok = 0
    fetch_state = "ok"
    try:
        resp = session.get(url, timeout=HTTP_TIMEOUT)
        transport_ok = 1
        if resp.status_code == 404:
            fetch_state = "http404"
        elif not resp.ok:
            fetch_state = f"http{resp.status_code}"
        else:
            resp.encoding = resp.apparent_encoding or "utf-8"
            html = resp.text
    except Exception as exc:
        fetch_state = "request_error:" + type(exc).__name__
    observed = datetime.now(JST)
    mb = (deadline - observed).total_seconds() / 60.0
    info = inspect_beforeinfo(html)
    if fetch_state != "ok" and info["state"] == "fetch_empty":
        info["state"] = fetch_state
    return {
        "race_id": str(r["race_id"]),
        "venue": venue,
        "rno": rno,
        "mb": mb,
        "bucket": bucket(mb),
        "transport_ok": transport_ok,
        **info,
    }


def main():
    if not DB:
        raise RuntimeError("DATABASE_URL is required")
    now = datetime.now(JST)
    print(f"BAO_EXLIVE_MODE=official_direct_read_only target:{TARGET_DATE} now:{now.isoformat()}", flush=True)
    print(
        f"BAO_EXLIVE_WINDOW=past:{PAST_MIN:.1f} future:{FUTURE_MIN:.1f} "
        f"strategy:one_per_bucket timeout:{HTTP_TIMEOUT:.1f}",
        flush=True,
    )
    print("BAO_EXLIVE_SOURCE=official_beforeinfo_no_db_snapshot_timestamps", flush=True)
    print("BAO_EXLIVE_HTTP_POLICY=sequential_low_load_no_retry", flush=True)
    print("BAO_EXLIVE_POLICY=no_writes_no_production_no_line", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute(
                """select race_id,coalesce(venue_id,venue_code) venue_id,race_no,deadline_at
                   from v2_races
                   where race_date=%s and deadline_at is not null
                     and deadline_at >= %s and deadline_at <= %s
                   order by deadline_at""",
                (TARGET_DATE, now - timedelta(minutes=PAST_MIN), now + timedelta(minutes=FUTURE_MIN)),
            )
            races = [dict(x) for x in c.fetchall()]

    targets = select_one_per_bucket(races, now)
    print(f"BAO_EXLIVE_CANDIDATES={len(races)}", flush=True)
    print(f"BAO_EXLIVE_TARGETS={len(targets)}", flush=True)

    bins = defaultdict(lambda: {"n": 0, "ready": 0, "lanes6": 0, "time6": 0})
    ready_total = 0
    transport_ok = 0
    session = requests.Session()
    session.headers.update(HEADERS)
    for r in targets:
        x = fetch_one(session, r)
        b = x["bucket"]
        bins[b]["n"] += 1
        bins[b]["ready"] += x["rank_ready"]
        bins[b]["lanes6"] += int(x["lanes"] == 6)
        bins[b]["time6"] += int(x["time_values"] == 6)
        ready_total += x["rank_ready"]
        transport_ok += x["transport_ok"]
        print(
            f"BAO_EXLIVE_RACE=race:{x['race_id']} venue:{x['venue']} rno:{x['rno']} "
            f"mb:{x['mb']:.2f} bucket:{b} state:{x['state']} transport_ok:{x['transport_ok']} "
            f"lanes:{x['lanes']} time_values:{x['time_values']} rank_ready:{x['rank_ready']}",
            flush=True,
        )

    for b in BUCKET_ORDER:
        s = bins[b]
        if s["n"]:
            print(
                f"BAO_EXLIVE_BIN={b} probed:{s['n']} lanes6:{s['lanes6']} "
                f"time6:{s['time6']} rank_ready:{s['ready']}",
                flush=True,
            )
    failures = len(targets) - transport_ok
    print(f"BAO_EXLIVE_TRANSPORT=ok:{transport_ok} failed:{failures}", flush=True)
    print(f"BAO_EXLIVE_SUMMARY=probed:{len(targets)} rank_ready:{ready_total}", flush=True)
    verdict = "OBSERVED" if transport_ok else "INCONCLUSIVE_TRANSPORT"
    print(f"BAO_EXLIVE_VERDICT={verdict}", flush=True)
    print("BAO_EXLIVE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
