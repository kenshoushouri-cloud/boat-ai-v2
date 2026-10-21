# -*- coding: utf-8 -*-
"""Strict READ-ONLY preview of the last 3連単不成立 K/HTML result.

Prepares the intended new v2_results row but does not write any data.
A different, backup-gated command will be required for any eventual INSERT.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import os
import sys

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import audit_k_day_all_pg as ka
import repair_month_all_pg as rm

DAY = "2026-10-08"
RID = "20261008_14_05"
EXPECTED = (
    ("20261008_", "20261009_", 144, 864, 143),
    ("20261015_", "20261016_", 156, 936, 156),
    ("20261016_", "20261017_", 156, 936, 156),
    ("20261017_", "20261018_", 168, 1008, 168),
)

def get_k():
    ka.TARGET_DATE = DAY
    text = ka.get_k_text(DAY)
    all_rows = [r for block in ka.split_venue_sections(text.splitlines())
                for r in ka.parse_section(block)]
    ids = [r["race_id"] for r in all_rows]
    if (len(ids) != 144 or len(set(ids)) != 144 or
            len([i for i in ids if i == RID]) != 1):
        raise RuntimeError("STOP: official K daily count/uniqueness differs")
    k = next(r for r in all_rows if r["race_id"] == RID)
    statuses = tuple((int(e["lane"]), str(e["finish_status"]),
                      e["finish_position"]) for e in
                     sorted(k["entries"], key=lambda x: int(x["lane"])))
    expected_statuses = (
        (1, "01", 1), (2, "F", None), (3, "S0", None),
        (4, "F", None), (5, "02", 2), (6, "S2", None),
    )
    if (statuses != expected_statuses or
            k["parse_failed_candidate_lines"] or
            k["trifecta_ticket"] is not None or
            k["trifecta_payout"] is not None or
            k["finish_order"] != "1-5" or
            str(k["venue_code"]) != "14" or int(k["race_no"]) != 5):
        raise RuntimeError("STOP: K special case differs from audited evidence")
    roster = sorted((int(e["lane"]), int(e["racer_number"]))
                    for e in k["entries"])
    return roster, statuses

def get_html():
    url = rm._official_url("raceresult", DAY, "14", 5)
    html = rm._fetch(url)
    if not html or rm._looks_no_race(html):
        raise RuntimeError("STOP: official result page unavailable")
    result = rm.parse_result(html)
    if (result.get("result_status") != "trifecta_invalid" or
            result.get("race_status") != "official" or
            result.get("trifecta_ticket") is not None or
            result.get("trifecta_payout_yen") != 0):
        raise RuntimeError("STOP: official HTML does not prove trifecta invalid")
    roster_page = rm._fetch(rm._official_url("racelist", DAY, "14", 5))
    if not roster_page or rm._looks_no_race(roster_page):
        raise RuntimeError("STOP: official racer list unavailable")
    html_roster = sorted((int(x["lane"]), int(x["racer_number"]))
                         for x in rm.parse_entries(roster_page, RID))
    return html_roster

def db_gate(k_roster):
    with psycopg.connect(
        "postgresql:///railway",
        options="-c default_transaction_read_only=on -c statement_timeout=15000"
    ) as conn:
        with conn.cursor() as cur:
            for lo, hi, races, entries, results in EXPECTED:
                cur.execute(
                    "SELECT "
                    "(SELECT count(*) FROM public.v2_races WHERE race_id >= %s AND race_id < %s),"
                    "(SELECT count(*) FROM public.v2_race_entries WHERE race_id >= %s AND race_id < %s),"
                    "(SELECT count(*) FROM public.v2_results WHERE race_id >= %s AND race_id < %s)",
                    (lo,hi,lo,hi,lo,hi)
                )
                actual = tuple(cur.fetchone())
                print(f"DAY_STATE {lo[:8]} {actual} expected={(races,entries,results)}",flush=True)
                if actual != (races, entries, results):
                    raise RuntimeError("STOP: DB daily counts have changed")
            cur.execute(
                "SELECT lane,racer_number FROM public.v2_race_entries "
                "WHERE race_id=%s ORDER BY lane", (RID,)
            )
            roster = [(int(a), int(b)) for a, b in cur.fetchall()]
            cur.execute("SELECT count(*) FROM public.v2_races WHERE race_id=%s", (RID,))
            race_count = int(cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM public.v2_results WHERE race_id=%s", (RID,))
            result_count = int(cur.fetchone()[0])
            cur.execute(
                "SELECT count(*) FROM public.v2_result_entries WHERE race_id=%s",
                (RID,)
            )
            details = int(cur.fetchone()[0])
            if (race_count != 1 or result_count != 0 or details != 0 or
                    len(roster) != 6 or roster != k_roster):
                raise RuntimeError("STOP: race/roster/existing-result differs")
            cur.execute(
                "SELECT column_name,udt_name,is_nullable,column_default "
                "FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='v2_results'"
            )
            cols = {name: (dtype,nullable,default)
                    for name,dtype,nullable,default in cur.fetchall()}
            fields = {
                "race_id": "text", "race_date": "date",
                "venue_code": "text", "race_no": "int4",
                "trifecta_ticket": "text", "trifecta_payout_yen": "int4",
                "result_status": "text", "race_status": "text",
                "official": "bool", "source": "text", "raw": "jsonb",
            }
            for col, kind in fields.items():
                if col not in cols or cols[col][0] != kind:
                    raise RuntimeError(f"STOP: incompatible {col} column")
            if (cols["trifecta_ticket"][1] != "YES" or
                    cols["trifecta_payout_yen"][1] != "YES"):
                raise RuntimeError("STOP: cannot represent invalid 3-ren-tan")
            absent_required = [
                name for name,(_,nullable,default) in cols.items()
                if nullable=="NO" and default is None and name!="race_id"
            ]
            if absent_required:
                raise RuntimeError("STOP: unknown required result columns: " +
                                   str(absent_required))
    print("DB_ABSENCE_AND_SCHEMA_PASS",flush=True)

def main():
    if os.geteuid() == 0:
        raise SystemExit("STOP: postgres account required")
    print("MODE=READ_ONLY_SPECIAL_RESULT_INSERT_PREVIEW",flush=True)
    k_roster, statuses = get_k()
    html_roster = get_html()
    if html_roster != k_roster:
        raise RuntimeError("STOP: K, official roster mismatch")
    print("OFFICIAL_K_HTML_ROSTER_AND_INVALID_STATUS_MATCH",flush=True)
    db_gate(k_roster)
    print("WOULD_INSERT_RACE_ID=" + RID,flush=True)
    print("WOULD_INSERT_STATUS=trifecta_invalid RACE_STATUS=official",flush=True)
    print("WOULD_INSERT_TICKET=None PAYOUT_YEN=0",flush=True)
    print("WOULD_INSERT_RACE_DATE=" + date.fromisoformat(DAY).isoformat(),flush=True)
    print("WOULD_PRESERVE_K_FINISH_ORDER=1-5",flush=True)
    print("WOULD_PRESERVE_K_LANE_STATUSES=" + str(statuses),flush=True)
    print("EXCLUDE_FROM_NORMAL_TRIFECTA_WIN_LOSS_AND_ROI",flush=True)
    print("SPECIAL_INSERT_PREVIEW_PASS_NO_DB_WRITES",flush=True)
    print("HISTORICAL_RETRIEVAL_NOT_PREDECISION",flush=True)

if __name__ == "__main__":
    main()
