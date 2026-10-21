# -*- coding: utf-8 -*-
"""Guarded INSERT-only 1-result pilot for historical 2026-10-08 K data.

Two gates required: --apply and CONFIRM_V5_RESULTS_INSERT=YES.
Only v2_results may be inserted; never UPDATE/DELETE or touch other tables.
The record is POST-RACE HISTORICAL data, NOT verified predeadline evidence.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import psycopg
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import audit_k_day_all_pg as ka
import repair_month_all_pg as rm

DAY = "2026-10-08"
RID = "20261008_01_01"
K_RACES = 144
BEFORE_RESULTS = 0
EXPECTED_TICKET = "3-6-5"
EXPECTED_PAYOUT = 27820
DB = "postgresql:///railway"


def official_evidence():
    ka.TARGET_DATE = DAY
    txt = ka.get_k_text(DAY)
    parsed = [row for venue in ka.split_venue_sections(txt.splitlines())
              for row in ka.parse_section(venue)]
    ids = [r["race_id"] for r in parsed]
    if len(ids) != K_RACES or len(set(ids)) != K_RACES or any(
        not x.startswith("20261008_") for x in ids
    ):
        raise RuntimeError("STOP: K count/duplicate/date changed")
    data = {r["race_id"]: r for r in parsed}
    k = data[RID]
    k_lanes = sorted((int(e["lane"]), int(e["racer_number"]))
                     for e in k["entries"])
    if (k_lanes != sorted(k_lanes) or [x[0] for x in k_lanes] != list(range(1, 7))
            or k["parse_failed_candidate_lines"]
            or k["trifecta_ticket"] != EXPECTED_TICKET
            or int(k["trifecta_payout"]) != EXPECTED_PAYOUT):
        raise RuntimeError("STOP: official K race evidence mismatch")

    venue, race_no = "01", 1
    roster_html = rm._fetch(rm._official_url("racelist", DAY, venue, race_no))
    result_html = rm._fetch(rm._official_url("raceresult", DAY, venue, race_no))
    if (not roster_html or not result_html or
        rm._looks_no_race(roster_html) or rm._looks_no_race(result_html)):
        raise RuntimeError("STOP: official HTML unavailable")
    html_lanes = sorted((int(e["lane"]), int(e["racer_number"]))
                        for e in rm.parse_entries(roster_html, RID))
    if html_lanes != k_lanes:
        raise RuntimeError("STOP: official HTML vs K roster mismatch")
    result = rm.parse_result(result_html)
    if (result.get("result_status") != "official"
        or result.get("trifecta_ticket") != EXPECTED_TICKET
        or int(result.get("trifecta_payout_yen") or 0) != EXPECTED_PAYOUT):
        raise RuntimeError("STOP: K vs HTML official result mismatch")
    return k_lanes, result


def day_state(cur):
    cur.execute("SELECT count(*) FROM public.v2_races "
                "WHERE race_id >= '20261008_' AND race_id < '20261009_'")
    races = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM public.v2_results "
                "WHERE race_id >= '20261008_' AND race_id < '20261009_'")
    results = cur.fetchone()[0]
    return (int(races), int(results))


def check_roster_and_absence(cur, official):
    cur.execute("SELECT lane,racer_number FROM public.v2_race_entries "
                "WHERE race_id=%s ORDER BY lane", (RID,))
    rows = [(int(l), int(n)) for l, n in cur.fetchall()]
    if rows != official:
        raise RuntimeError("STOP: DB/K/HTML six-racer mismatch")
    cur.execute("SELECT count(*) FROM public.v2_results WHERE race_id=%s", (RID,))
    if int(cur.fetchone()[0]) != 0:
        raise RuntimeError("STOP: pilot result already exists, do NOT overwrite")


def insert_one(cur, result):
    cur.execute(
        "SELECT column_name,data_type FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='v2_results'")
    schema = dict(cur.fetchall())
    wanted = {
        "race_id": RID, "race_date": DAY, "venue_code": "01",
        "race_no": 1, "trifecta_ticket": EXPECTED_TICKET,
        "trifecta_payout_yen": EXPECTED_PAYOUT,
        "result_status": "official", "race_status": "official",
        "official": True, "source": "official_historical_recovery",
        "fetched_at": rm._now_iso(),
    }
    # Retain legacy payout if a compatible numeric legacy column exists.
    if schema.get("trifecta_payout") in (
        "smallint", "integer", "bigint", "numeric", "double precision", "real"
    ):
        wanted["trifecta_payout"] = EXPECTED_PAYOUT
    for name in ("first_lane", "second_lane", "third_lane",
                 "fourth_lane", "fifth_lane", "sixth_lane"):
        if name in schema and result.get(name) is not None:
            wanted[name] = result[name]
    required = {"race_id", "trifecta_ticket", "trifecta_payout_yen",
                "result_status", "source"}
    if not required.issubset(schema) or not set(wanted).issubset(schema):
        raise RuntimeError("STOP: schema changed")
    keys = list(wanted)
    query = sql.SQL("INSERT INTO public.v2_results ({}) VALUES ({}) RETURNING race_id").format(
        sql.SQL(",").join(map(sql.Identifier, keys)),
        sql.SQL(",").join(sql.Placeholder() for _ in keys))
    cur.execute(query, [wanted[k] for k in keys])
    if cur.fetchone() != (RID,):
        raise RuntimeError("STOP: insert RETURNING mismatch")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    a = parser.parse_args()
    if os.geteuid() == 0:
        raise RuntimeError("STOP: run as postgres")
    if a.apply and os.environ.get("CONFIRM_V5_RESULTS_INSERT") != "YES":
        raise RuntimeError("STOP: explicit INSERT confirmation missing")
    roster, result = official_evidence()
    print("OFFICIAL_K_HTML_MATCH=1 RACE=" + RID, flush=True)
    opts = ("-c statement_timeout=15000" if a.apply else
            "-c default_transaction_read_only=on -c statement_timeout=15000")
    with psycopg.connect(DB, autocommit=True, options=opts) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='3s'")
                if a.apply:
                    cur.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s),hashtext(%s))",
                                ("v5_k_results_insert", RID))
                    if cur.fetchone() != (True,):
                        raise RuntimeError("STOP: pilot lock already held")
                pre = day_state(cur)
                if pre != (K_RACES, BEFORE_RESULTS):
                    raise RuntimeError("STOP: day race/result counts changed " + str(pre))
                check_roster_and_absence(cur, roster)
                if not a.apply:
                    print("MODE=READ_ONLY PRE=" + str(pre), flush=True)
                    print("RESULT_ONE_PREVIEW_OK_NO_DB_WRITES", flush=True)
                    return
                insert_one(cur, result)
                check = day_state(cur)
                cur.execute("SELECT result_status,trifecta_ticket,trifecta_payout_yen,source "
                            "FROM public.v2_results WHERE race_id=%s", (RID,))
                row = cur.fetchone()
                if (check != (K_RACES, BEFORE_RESULTS + 1) or
                    row != ("official", EXPECTED_TICKET, EXPECTED_PAYOUT,
                            "official_historical_recovery")):
                    raise RuntimeError("STOP: postwrite mismatch; rollback")
                print("TRANSACTION_VALIDATED PRE=" + str(pre) + " POST=" + str(check), flush=True)
    if a.apply:
        with psycopg.connect(
            DB, options="-c default_transaction_read_only=on -c statement_timeout=15000"
        ) as c:
            with c.cursor() as cur:
                state = day_state(cur)
                cur.execute("SELECT trifecta_ticket,trifecta_payout_yen FROM public.v2_results "
                            "WHERE race_id=%s", (RID,))
                val = cur.fetchone()
                if state != (K_RACES, 1) or val != (EXPECTED_TICKET, EXPECTED_PAYOUT):
                    raise RuntimeError("STOP: postcommit verification mismatch; do not rerun")
        print("RESULT_ONE_INSERT_VERIFIED_NO_EXISTING_UPDATES", flush=True)
        print("HISTORICAL_RETRIEVAL_NOT_PREDECISION", flush=True)


if __name__ == "__main__":
    main()
