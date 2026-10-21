# -*- coding: utf-8 -*-
"""Bounded, result-only historical K recovery for ConoHa.
Default is READ ONLY. --apply plus CONFIRM_V5_RESULTS_INSERT=YES required to write.
Existing v2_results rows never updated or deleted. NO entry/race/model writes.
Official historical results are NOT pre-deadline model evidence.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta
import fcntl
import os
from pathlib import Path
import re
import sys
import time

import psycopg
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import audit_k_day_all_pg as ka
import repair_month_all_pg as rm

DB = "postgresql:///railway"
LOCK = "/tmp/boat_v5_results_bounded.lock"
DAY_RACES = {"2026-10-08": 144, "2026-10-15": 156,
             "2026-10-16": 156, "2026-10-17": 168}
SOURCE = "official_historical_recovery"
FINS = ("first_lane", "second_lane", "third_lane",
        "fourth_lane", "fifth_lane", "sixth_lane")


def bounds(day):
    return day.replace("-", "") + "_", (date.fromisoformat(day) + timedelta(days=1)).strftime("%Y%m%d") + "_"


def official_k(day):
    ka.TARGET_DATE = day
    body = ka.get_k_text(day)
    parsed = [race for section in ka.split_venue_sections(body.splitlines())
              for race in ka.parse_section(section)]
    ids = [r["race_id"] for r in parsed]
    if len(ids) != DAY_RACES[day] or len(set(ids)) != len(ids) or any(
        not rid.startswith(day.replace("-", "") + "_") for rid in ids
    ):
        raise RuntimeError("STOP: official K race set mismatch")
    for race in parsed:
        lanes = [int(e["lane"]) for e in race["entries"]]
        if sorted(lanes) != list(range(1, 7)) or race["parse_failed_candidate_lines"]:
            raise RuntimeError("STOP: K roster/parse issue " + race["race_id"])
    return {r["race_id"]: r for r in parsed}


def snapshot(day):
    lo, hi = bounds(day)
    with psycopg.connect(
        DB, options="-c default_transaction_read_only=on -c statement_timeout=15000"
    ) as c:
        with c.cursor() as cur:
            cur.execute("SELECT race_id FROM public.v2_races WHERE race_id >= %s AND race_id < %s",
                        (lo, hi))
            races = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT race_id,lane,racer_number FROM public.v2_race_entries "
                        "WHERE race_id >= %s AND race_id < %s", (lo, hi))
            rosters = defaultdict(list)
            for rid, lane, num in cur.fetchall():
                rosters[rid].append((int(lane), int(num)))
            cur.execute("SELECT race_id,trifecta_ticket,trifecta_payout_yen,source "
                        "FROM public.v2_results WHERE race_id >= %s AND race_id < %s",
                        (lo, hi))
            results = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}
    return races, {rid: sorted(rows) for rid, rows in rosters.items()}, results


def verify_state(day, k, state, expected):
    races, rosters, results = state
    if len(races) != DAY_RACES[day] or set(k) != races or len(results) != expected:
        raise RuntimeError("STOP: race/result count or official ID set changed")
    for rid in races:
        db = sorted(rosters.get(rid, []))
        kr = sorted((int(e["lane"]), int(e["racer_number"])) for e in k[rid]["entries"])
        if len(db) != 6 or db != kr:
            raise RuntimeError("STOP: K/DB racer mismatch " + rid)
    for rid, (ticket, payout, _) in results.items():
        o = k[rid]
        if ((ticket is not None and ticket != o.get("trifecta_ticket")) or
            (payout is not None and int(payout) > 0 and
             int(payout) != int(o.get("trifecta_payout") or 0))):
            raise RuntimeError("STOP: existing result conflicts with K " + rid)
    return results


def eligible_ids(k, existing):
    pending = sorted(set(k) - set(existing))
    valid, unusual = [], []
    for rid in pending:
        ticket = k[rid].get("trifecta_ticket")
        payout = int(k[rid].get("trifecta_payout") or 0)
        parts = str(ticket or "").split("-")
        if (len(parts) == 3 and all(x in "123456" for x in parts)
                and len(set(parts)) == 3 and payout > 0):
            valid.append(rid)
        else:
            unusual.append(rid)
    return valid, unusual


def fetch_triple(day, rid, k, roster):
    m = re.fullmatch(r"\d{8}_(\d{2})_(\d{2})", rid)
    if not m or not rid.startswith(day.replace("-", "") + "_"):
        raise RuntimeError("STOP: bad race ID")
    venue, number = m[1], int(m[2])
    list_html = rm._fetch(rm._official_url("racelist", day, venue, number))
    result_html = rm._fetch(rm._official_url("raceresult", day, venue, number))
    if not list_html or not result_html or rm._looks_no_race(list_html) or rm._looks_no_race(result_html):
        raise RuntimeError("STOP: official HTML unavailable " + rid)
    html_roster = sorted((int(e["lane"]), int(e["racer_number"]))
                         for e in rm.parse_entries(list_html, rid))
    if html_roster != sorted(roster):
        raise RuntimeError("STOP: HTML/K/DB racer mismatch " + rid)
    result = rm.parse_result(result_html)
    if (result.get("result_status") != "official"
            or result.get("trifecta_ticket") != k["trifecta_ticket"]
            or int(result.get("trifecta_payout_yen") or 0) != int(k["trifecta_payout"])):
        raise RuntimeError("STOP: K/HTML trifecta mismatch " + rid)
    return result


def insert_one(conn, day, rid, k, roster, result):
    m = re.fullmatch(r"\d{8}_(\d{2})_(\d{2})", rid)
    if not m:
        raise RuntimeError("STOP: race ID malformed")
    values = {
        "race_id": rid, "race_date": day,
        "venue_code": m[1], "race_no": int(m[2]),
        "trifecta_ticket": k["trifecta_ticket"],
        "trifecta_payout_yen": int(k["trifecta_payout"]),
        "result_status": "official", "race_status": "official",
        "official": True, "source": SOURCE, "fetched_at": rm._now_iso(),
    }
    for name in FINS:
        if result.get(name) is not None:
            values[name] = result[name]
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout='3s'")
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s),hashtext(%s))",
                        ("v5_missing_results", rid))
            if cur.fetchone() != (True,):
                raise RuntimeError("STOP: another writer holds lock " + rid)
            cur.execute("SELECT count(*) FROM public.v2_races WHERE race_id=%s", (rid,))
            if cur.fetchone()[0] != 1:
                raise RuntimeError("STOP: race not exactly once " + rid)
            cur.execute("SELECT lane,racer_number FROM public.v2_race_entries "
                        "WHERE race_id=%s ORDER BY lane", (rid,))
            if [(int(l), int(n)) for l, n in cur.fetchall()] != sorted(roster):
                raise RuntimeError("STOP: roster changed during insert " + rid)
            cur.execute("SELECT count(*) FROM public.v2_results WHERE race_id=%s", (rid,))
            if cur.fetchone()[0] != 0:
                raise RuntimeError("STOP: existing result; never overwrite " + rid)
            cur.execute("SELECT column_name,data_type FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='v2_results'")
            schema = dict(cur.fetchall())
            required = {"race_id", "race_date", "venue_code", "race_no",
                        "trifecta_ticket", "trifecta_payout_yen", "result_status",
                        "race_status", "official", "source", "fetched_at"}
            if not required.issubset(schema) or not set(values).issubset(schema):
                raise RuntimeError("STOP: unexpected DB result schema")
            if schema.get("trifecta_payout") in {
                "smallint", "integer", "bigint", "numeric", "double precision", "real"
            }:
                values["trifecta_payout"] = int(k["trifecta_payout"])
            keys = list(values)
            cur.execute(
                sql.SQL("INSERT INTO public.v2_results ({}) VALUES ({}) RETURNING race_id").format(
                    sql.SQL(",").join(sql.Identifier(x) for x in keys),
                    sql.SQL(",").join(sql.Placeholder() for _ in keys)),
                [values[x] for x in keys],
            )
            if cur.fetchone() != (rid,):
                raise RuntimeError("STOP: INSERT RETURNING mismatch")
            cur.execute("SELECT result_status,trifecta_ticket,trifecta_payout_yen,source "
                        "FROM public.v2_results WHERE race_id=%s", (rid,))
            if cur.fetchone() != ("official", k["trifecta_ticket"], int(k["trifecta_payout"]), SOURCE):
                raise RuntimeError("STOP: post-insert mismatch; rollback")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--day", choices=list(DAY_RACES), required=True)
    p.add_argument("--expected-results", type=int, required=True)
    p.add_argument("--limit", type=int, default=24)
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if os.geteuid() == 0:
        raise SystemExit("STOP: run as postgres")
    if not (1 <= args.limit <= 24 and 0 <= args.expected_results <= DAY_RACES[args.day]):
        raise SystemExit("STOP: invalid limit or expected results")
    if args.apply and os.environ.get("CONFIRM_V5_RESULTS_INSERT") != "YES":
        raise SystemExit("STOP: explicit apply gate missing")

    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("STOP: another bounded results run active")
        k = official_k(args.day)
        original = snapshot(args.day)
        before_results = verify_state(args.day, k, original, args.expected_results)
        valid, unusual = eligible_ids(k, before_results)
        selected = valid[:args.limit]
        if not selected:
            raise RuntimeError("STOP: no eligible standard results remain")
        print(f"MODE={'APPLY' if args.apply else 'READ_ONLY'} DAY={args.day} "
              f"RACES={len(original[0])} RESULTS={len(before_results)} "
              f"ELIGIBLE={len(valid)} NONSTANDARD={len(unusual)} "
              f"SELECTED={len(selected)}", flush=True)
        if unusual:
            print("NONSTANDARD_SAMPLES=" + str(unusual[:3]), flush=True)
        print("FIRST=" + selected[0] + " LAST=" + selected[-1], flush=True)

        # No writes until every candidate's official HTML/K/DB evidence agrees.
        checked = []
        for n, rid in enumerate(selected, 1):
            checked.append((rid, fetch_triple(args.day, rid, k[rid], original[1][rid])))
            if n % 6 == 0 or n == len(selected):
                print(f"HTML_PRECHECK_VERIFIED={n}/{len(selected)} day={args.day}", flush=True)
        if snapshot(args.day) != original:
            raise RuntimeError("STOP: DB changed during official precheck; rerun only after audit")
        print("ALL_SELECTED_K_HTML_DB_VERIFIED=" + str(len(checked)), flush=True)
        if not args.apply:
            print("RESULTS_BATCH_PREVIEW_PASS_NO_DB_WRITES", flush=True)
            print("HISTORICAL_RETRIEVAL_NOT_PREDECISION", flush=True)
            return

        with psycopg.connect(DB, autocommit=True, options="-c statement_timeout=15000") as conn:
            for number, (rid, result) in enumerate(checked, 1):
                insert_one(conn, args.day, rid, k[rid], original[1][rid], result)
                if number % 6 == 0 or number == len(checked):
                    state = snapshot(args.day)
                    after_results = verify_state(args.day, k, state, len(before_results) + number)
                    if (set(before_results) - set(after_results) or
                        any(after_results[x] != before_results[x] for x in before_results)):
                        raise RuntimeError("STOP: an existing result changed; do not rerun")
                    print(f"RESULTS_BATCH_PASS added={number} results={len(after_results)}", flush=True)
                time.sleep(0.15)
        print("RESULTS_BATCH_APPLY_VERIFIED added=" + str(len(checked)), flush=True)
        print("HISTORICAL_RETRIEVAL_NOT_PREDECISION", flush=True)
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
