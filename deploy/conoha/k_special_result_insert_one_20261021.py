# -*- coding: utf-8 -*-
"""Guarded INSERT-only result for one historical 3連単不成立 race.

Never invent a valid trifecta ticket. Explicit --apply + environment gate.
Only public.v2_results may receive one row; never UPDATE/DELETE.
"""
from __future__ import annotations

import argparse
import os

import psycopg
from psycopg.types.json import Jsonb

import k_special_result_insert_preview_20261021 as pre

RID = pre.RID
DAY = pre.DAY
SOURCE = "official_historical_special_recovery"

def verify_state(cur, official_roster, *, expected_results):
    for lo, hi, races, entries, results in pre.EXPECTED:
        if lo == "20261008_":
            results = expected_results
        cur.execute(
            "SELECT "
            "(SELECT count(*) FROM public.v2_races WHERE race_id >= %s AND race_id < %s),"
            "(SELECT count(*) FROM public.v2_race_entries WHERE race_id >= %s AND race_id < %s),"
            "(SELECT count(*) FROM public.v2_results WHERE race_id >= %s AND race_id < %s)",
            (lo, hi, lo, hi, lo, hi),
        )
        actual = tuple(int(x) for x in cur.fetchone())
        if actual != (races, entries, results):
            raise RuntimeError("STOP: day count mismatch " + lo + " " + str(actual))
    cur.execute("SELECT lane,racer_number FROM public.v2_race_entries "
                "WHERE race_id=%s ORDER BY lane", (RID,))
    roster = [(int(a), int(b)) for a,b in cur.fetchall()]
    if roster != official_roster:
        raise RuntimeError("STOP: DB/K/HTML roster mismatch")
    cur.execute("SELECT count(*) FROM public.v2_races WHERE race_id=%s", (RID,))
    if int(cur.fetchone()[0]) != 1:
        raise RuntimeError("STOP: race row missing")
    cur.execute("SELECT count(*) FROM public.v2_result_entries WHERE race_id=%s", (RID,))
    if int(cur.fetchone()[0]) != 0:
        raise RuntimeError("STOP: unexpected result details")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if os.geteuid() == 0:
        raise RuntimeError("STOP: run as postgres, never root")
    if not args.apply:
        print("NO_APPLY_FLAG=READ_ONLY; use the existing special preview", flush=True)
        pre.main()
        return
    if os.getenv("CONFIRM_V5_SPECIAL_RESULT_INSERT") != RID:
        raise RuntimeError("STOP: explicit special-race confirmation missing")

    # Re-fetch and independently validate historical official K + two HTML pages.
    k_roster, statuses = pre.get_k()
    if pre.get_html() != k_roster:
        raise RuntimeError("STOP: official K vs HTML six-racer mismatch")
    pre.db_gate(k_roster)
    print("SPECIAL_OFFICIAL_AND_READONLY_PREFLIGHT_PASS", flush=True)

    raw = {
        "source_context": "official_postrace_historical_retrieval_not_predecision",
        "special_trifecta_invalid": True,
        "exclude_from_standard_trifecta_win_loss_roi": True,
        "official_k_finish_order_partial": "1-5",
        "official_k_lane_statuses": [
            {"lane": lane, "finish_status": status, "finish_position": pos}
            for lane,status,pos in statuses
        ],
        "official_html_result_status": "trifecta_invalid",
        "official_html_race_status": "official",
        "official_html_trifecta_ticket": None,
        "official_html_trifecta_payout_yen": 0,
    }
    cols = (
        "race_id,race_date,venue_code,race_no,result_status,race_status,"
        "trifecta_ticket,trifecta_payout_yen,finish_order,official,"
        "source,fetched_at,raw"
    )
    vals = (
        RID, DAY, "14", 5, "trifecta_invalid", "official",
        None, 0, "1-5", True, SOURCE, pre.rm._now_iso(), Jsonb(raw),
    )

    with psycopg.connect(
        "postgresql:///railway",
        autocommit=True,
        options="-c statement_timeout=15000",
    ) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='3s'")
                cur.execute(
                    "SELECT pg_try_advisory_xact_lock(hashtext(%s),hashtext(%s))",
                    ("v5_k_results_insert", RID),
                )
                if cur.fetchone() != (True,):
                    raise RuntimeError("STOP: special result lock unavailable")
                verify_state(cur, k_roster, expected_results=143)
                cur.execute("SELECT count(*) FROM public.v2_results WHERE race_id=%s", (RID,))
                if int(cur.fetchone()[0]) != 0:
                    raise RuntimeError("STOP: result already exists, no overwrite")
                cur.execute(
                    "INSERT INTO public.v2_results (" + cols + ") "
                    "VALUES (" + ",".join(["%s"] * len(vals)) + ") "
                    "RETURNING race_id",
                    vals,
                )
                if cur.fetchone() != (RID,):
                    raise RuntimeError("STOP: unexpected INSERT RETURNING")
                verify_state(cur, k_roster, expected_results=144)
                cur.execute(
                    "SELECT result_status,race_status,trifecta_ticket,"
                    "trifecta_payout_yen,official,source,finish_order,"
                    "raw->>'exclude_from_standard_trifecta_win_loss_roi' "
                    "FROM public.v2_results WHERE race_id=%s", (RID,)
                )
                expected = ("trifecta_invalid", "official", None, 0,
                            True, SOURCE, "1-5", "true")
                if cur.fetchone() != expected:
                    raise RuntimeError("STOP: inserted special row mismatch; rollback")
                print("TRANSACTION_VALIDATED_SPECIAL_RESULT_1", flush=True)

    # Verify after commit without altering the database.
    with psycopg.connect(
        "postgresql:///railway",
        options="-c default_transaction_read_only=on -c statement_timeout=15000",
    ) as conn:
        with conn.cursor() as cur:
            verify_state(cur, k_roster, expected_results=144)
            cur.execute(
                "SELECT result_status,trifecta_ticket,trifecta_payout_yen "
                "FROM public.v2_results WHERE race_id=%s", (RID,)
            )
            if cur.fetchone() != ("trifecta_invalid", None, 0):
                raise RuntimeError("STOP: postcommit special row mismatch; do not rerun")
    print("SPECIAL_RESULT_ONE_INSERT_VERIFIED_NO_EXISTING_UPDATES", flush=True)
    print("ALL_FOUR_DAYS_OFFICIAL_RESULTS_ACCOUNTED_FOR", flush=True)
    print("NOTE: downstream ROI consumers still require status-filter audit", flush=True)
    print("HISTORICAL_RETRIEVAL_NOT_PREDECISION", flush=True)

if __name__ == "__main__":
    main()
