# -*- coding: utf-8 -*-
"""One-race read-only pilot for the missing official K result repair.

No writes: verify 2026-10-08 race/roster/K result against official HTML,
and display v2_results required columns before designing INSERT-only repair.
Historical retrieval is never evidence for a pre-deadline prediction.
"""
import os
import re
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import audit_k_day_all_pg as ka
import repair_month_all_pg as rm

DAY = "2026-10-08"
EXPECTED_RACES = 144
EXPECTED_MISSING = 144
DB = "postgresql:///railway"


def main():
    if os.geteuid() == 0:
        raise RuntimeError("STOP: execute as postgres")
    print("MODE=RESULT_PILOT_READ_ONLY", flush=True)
    ka.TARGET_DATE = DAY
    text = ka.get_k_text(DAY)
    races = [r for v in ka.split_venue_sections(text.splitlines())
             for r in ka.parse_section(v)]
    official = {r["race_id"]: r for r in races}
    if (len(official) != EXPECTED_RACES or len(races) != EXPECTED_RACES or
            any(not rid.startswith("20261008_") for rid in official)):
        raise RuntimeError("STOP: K count/duplicate/date mismatch")

    with psycopg.connect(
        DB, options="-c default_transaction_read_only=on -c statement_timeout=15000"
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT race_id FROM public.v2_races "
                "WHERE race_id >= '20261008_' AND race_id < '20261009_'")
            existing = {r[0] for r in cur.fetchall()}
            cur.execute(
                "SELECT race_id FROM public.v2_results "
                "WHERE race_id >= '20261008_' AND race_id < '20261009_'")
            result_ids = {r[0] for r in cur.fetchall()}
            if existing != set(official) or len(existing - result_ids) != EXPECTED_MISSING:
                raise RuntimeError("STOP: race IDs or missing-result count changed")
            selected = [rid for rid in sorted(existing - result_ids)
                        if official[rid].get("trifecta_ticket")
                        and int(official[rid].get("trifecta_payout") or 0) > 0]
            if len(selected) != 143 or "20261008_14_05" in selected:
                raise RuntimeError("STOP: standard-vs-nonstandard result count changed")
            rid = selected[0]
            cur.execute(
                "SELECT lane, racer_number FROM public.v2_race_entries "
                "WHERE race_id=%s ORDER BY lane", (rid,))
            db_roster = [(int(lane), int(num)) for lane, num in cur.fetchall()]
            cur.execute(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns WHERE table_schema='public' "
                "AND table_name='v2_results' ORDER BY ordinal_position")
            cols = cur.fetchall()
            if not cols:
                raise RuntimeError("STOP: no result table schema found")
            mandatory = [c[0] for c in cols if c[2] == "NO" and c[3] is None]
            expected_result_cols = {"race_id", "result_status",
                                    "trifecta_ticket", "trifecta_payout_yen", "source"}
            if not expected_result_cols.issubset({c[0] for c in cols}):
                raise RuntimeError("STOP: unexpected result table columns")

    k = official[rid]
    k_roster = sorted((int(e["lane"]), int(e["racer_number"])) for e in k["entries"])
    if db_roster != k_roster or [x[0] for x in db_roster] != list(range(1, 7)):
        raise RuntimeError("STOP: K/DB roster mismatch")

    m = re.fullmatch(r"\d{8}_(\d{2})_(\d{2})", rid)
    if not m:
        raise RuntimeError("STOP: malformed race ID")
    venue, race_no = m[1], int(m[2])
    list_html = rm._fetch(rm._official_url("racelist", DAY, venue, race_no))
    result_html = rm._fetch(rm._official_url("raceresult", DAY, venue, race_no))
    if not list_html or not result_html or rm._looks_no_race(list_html) or rm._looks_no_race(result_html):
        raise RuntimeError("STOP: HTML page unavailable")
    html_roster = sorted(
        (int(e["lane"]), int(e["racer_number"]))
        for e in rm.parse_entries(list_html, rid))
    if db_roster != html_roster:
        raise RuntimeError("STOP: HTML/DB/K roster mismatch")
    html = rm.parse_result(result_html)
    ticket = k["trifecta_ticket"]
    payout = int(k["trifecta_payout"])
    if (html.get("result_status") != "official" or
        html.get("trifecta_ticket") != ticket or
        int(html.get("trifecta_payout_yen") or 0) != payout):
        raise RuntimeError("STOP: official HTML vs K result mismatch")

    print(f"DAY={DAY} K={len(official)} RESULTS_MISSING={EXPECTED_MISSING} STANDARD=143 NONSTANDARD=1")
    print(f"SELECTED={rid} TICKET={ticket} PAYOUT={payout} ROSTER=6")
    print("V2_RESULTS_MANDATORY=" + ",".join(mandatory))
    print("V2_RESULTS_COLUMNS=" + ",".join(c[0] for c in cols))
    print("RESULT_PILOT_READ_ONLY_PASS_NO_DB_WRITES")
    print("HISTORICAL_RETRIEVAL_NOT_PREDECISION")


if __name__ == "__main__":
    main()
