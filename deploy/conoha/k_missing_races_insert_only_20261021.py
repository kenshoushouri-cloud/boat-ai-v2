# -*- coding: utf-8 -*-
"""Safe incremental restoration of wholly absent historical K races on ConoHa.

Default: read-only plan. No DB writes until BOTH --apply and
CONFIRM_V5_K_RACE_REPAIR=YES. Only entirely missing 4-table race IDs are
eligible. Each race is an independent all-or-nothing 3-table INSERT transaction.
Do not use historical retrieval as a pre-deadline feature snapshot.
This intentionally does not restore v2_result_entries (separate K path).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import psycopg
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import audit_k_day_all_pg as ka
import repair_month_all_pg as rm

TABLES = ("v2_races", "v2_race_entries", "v2_results", "v2_result_entries")
BASE = "postgresql:///railway"
DAYS = ("2026-10-16", "2026-10-17")


def read_ids(cur, day):
    prefix = day.replace("-", "") + "_"
    end = (date.fromisoformat(day).toordinal() + 1)
    after = date.fromordinal(end).strftime("%Y%m%d") + "_"
    found = {}
    for table in TABLES:
        cur.execute(
            sql.SQL("SELECT DISTINCT race_id FROM public.{} WHERE race_id >= %s AND race_id < %s").format(
                sql.Identifier(table)
            ), (prefix, after),
        )
        found[table] = {str(x[0]) for x in cur.fetchall()}
    return found


def source_k(day):
    ka.TARGET_DATE = day
    body = ka.get_k_text(day)
    sections = ka.split_venue_sections(body.splitlines())
    parsed = [r for s in sections for r in ka.parse_section(s)]
    ids = [str(r["race_id"]) for r in parsed]
    if not ids or len(set(ids)) != len(ids):
        raise RuntimeError("STOP: official K empty or duplicate race ID")
    for r in parsed:
        lanes = [e["lane"] for e in r["entries"]]
        if (sorted(lanes) != list(range(1, 7))
                or r["parse_failed_candidate_lines"]):
            raise RuntimeError("STOP: official K parse or lane issue " + r["race_id"])
    return {r["race_id"]: r for r in parsed}


def insert_new(cur, table, data):
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s", (table,)
    )
    available = {c[0] for c in cur.fetchall()}
    keys = [k for k in data if k in available]
    if "race_id" not in keys:
        raise RuntimeError("STOP: missing race_id field for " + table)
    if table == "v2_race_entries" and not {"lane", "racer_number"}.issubset(keys):
        raise RuntimeError("STOP: roster schema mismatch")
    if table == "v2_results" and not {
        "result_status", "trifecta_ticket", "trifecta_payout_yen", "source",
    }.issubset(keys):
        raise RuntimeError("STOP: result schema mismatch")
    q = sql.SQL("INSERT INTO public.{} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(k) for k in keys),
        sql.SQL(", ").join(sql.Placeholder() for _ in keys),
    )
    cur.execute(q, [data[k] for k in keys])
    if cur.rowcount != 1:
        raise RuntimeError("STOP: one-row INSERT expected")


def save_one(conn, day, rid, k):
    match = re.fullmatch(r"(\d{8})_(\d{2})_(\d{2})", rid)
    if not match or match[1] != day.replace("-", ""):
        raise RuntimeError("STOP: invalid ID " + rid)
    venue, race_no = match[2], int(match[3])
    list_html = rm._fetch(rm._official_url("racelist", day, venue, race_no))
    if not list_html or rm._looks_no_race(list_html):
        raise RuntimeError("STOP: official racelist unavailable " + rid)
    entries = sorted(rm.parse_entries(list_html, rid), key=lambda e: e["lane"])
    racers = [int(e["racer_number"]) for e in entries]
    k_racers = {int(e["lane"]): int(e["racer_number"]) for e in k["entries"]}
    if (len(entries) != 6 or [e["lane"] for e in entries] != list(range(1, 7))
            or len(set(racers)) != 6 or
            any(k_racers[e["lane"]] != e["racer_number"] for e in entries)
            or any(not e.get("racer_class") for e in entries)):
        raise RuntimeError("STOP: official roster vs K mismatch " + rid)
    res_html = rm._fetch(rm._official_url("raceresult", day, venue, race_no))
    if not res_html or rm._looks_no_race(res_html):
        raise RuntimeError("STOP: official result unavailable " + rid)
    result = rm.parse_result(res_html)
    ticket = result.get("trifecta_ticket")
    payout = int(result.get("trifecta_payout_yen") or 0)
    if (result.get("result_status") != "official" or not ticket or payout <= 0
            or ticket != k["trifecta_ticket"] or payout != k["trifecta_payout"]):
        raise RuntimeError("STOP: K vs HTML result mismatch or nonstandard race " + rid)

    now = rm._now_iso()
    deadline = rm.parse_deadline_time(list_html, race_no)
    race = dict(race_id=rid, race_date=day, venue_code=venue, venue_id=venue,
                venue_name=rm.VENUE_NAMES[venue], race_no=race_no,
                race_name=rm.parse_race_name(list_html),
                deadline_time=deadline, deadline_at=rm.make_deadline_at(day, deadline),
                status="official", updated_at=now)
    result.update(race_id=rid, race_date=day,
                  source="official_historical_recovery", fetched_at=now)

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout='3s'")
            cur.execute("SET LOCAL statement_timeout='20s'")
            counts = []
            for table in TABLES:
                cur.execute(sql.SQL("SELECT count(*) FROM public.{} WHERE race_id=%s").format(
                    sql.Identifier(table)), (rid,))
                counts.append(int(cur.fetchone()[0]))
            if counts != [0, 0, 0, 0]:
                raise RuntimeError("STOP: DB changed, existing data " + rid + " " + str(counts))
            insert_new(cur, "v2_races", race)
            for e in entries:
                insert_new(cur, "v2_race_entries", {
                    "race_id": rid, "lane": e["lane"], "course": e["lane"],
                    "racer_number": e["racer_number"], "racer_class": e["racer_class"],
                    "racer_class_text": e.get("racer_class_text"), "updated_at": now,
                })
            insert_new(cur, "v2_results", result)
            cur.execute(
                "SELECT lane, racer_number FROM public.v2_race_entries "
                "WHERE race_id=%s ORDER BY lane", (rid,),
            )
            if cur.fetchall() != [(e["lane"], e["racer_number"]) for e in entries]:
                raise RuntimeError("STOP: postwrite roster mismatch " + rid)
            cur.execute(
                "SELECT trifecta_ticket, trifecta_payout_yen FROM public.v2_results "
                "WHERE race_id=%s", (rid,),
            )
            if cur.fetchone() != (ticket, payout):
                raise RuntimeError("STOP: postwrite result mismatch " + rid)
    print(f"DAY_RACE_PASS {rid} ticket={ticket} payout={payout}", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--day", choices=DAYS, required=True)
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if not 1 <= args.limit <= 6:
        raise SystemExit("STOP: --limit must be 1..6")
    if args.apply and os.environ.get("CONFIRM_V5_K_RACE_REPAIR") != "YES":
        raise SystemExit("STOP: explicit write gate missing")

    print("MODE=" + ("APPLY" if args.apply else "READ_ONLY"), flush=True)
    official = source_k(args.day)
    with psycopg.connect(
        BASE,
        autocommit=True,
        options=("-c statement_timeout=15000" if args.apply
                 else "-c default_transaction_read_only=on -c statement_timeout=15000"),
    ) as conn:
        with conn.cursor() as cur:
            found = read_ids(cur, args.day)
        existing_any = set().union(*found.values())
        extras = existing_any - set(official)
        if extras:
            raise RuntimeError("STOP: DB ID not in official K: " + str(sorted(extras)[:3]))
        missing = sorted(set(official) - existing_any)
        # Only ordinary positive-payoff official races are eligible in this version.
        eligible = [rid for rid in missing if official[rid].get("trifecta_ticket")
                    and int(official[rid].get("trifecta_payout") or 0) > 0]
        print(f"OFFICIAL={len(official)} ABSENT_ALL_FOUR={len(missing)} "
              f"ELIGIBLE_STANDARD={len(eligible)}", flush=True)
        print(f"SELECTED={eligible[:args.limit]}", flush=True)
        if not args.apply:
            print("DRY_RUN_DONE_NO_DB_WRITES", flush=True)
            return
        selected = eligible[:args.limit]
        if not selected:
            raise RuntimeError("STOP: nothing eligible")
        for index, rid in enumerate(selected):
            save_one(conn, args.day, rid, official[rid])
            if index + 1 < len(selected):
                time.sleep(2)
    print(f"BATCH_PASS wrote={len(selected)}", flush=True)
    print("HISTORICAL_RETRIEVAL_NOT_PREDECISION", flush=True)


if __name__ == "__main__":
    main()
