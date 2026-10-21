# -*- coding: utf-8 -*-
"""Investigate the only nonstandard official K result. READ ONLY; no DB writes."""
from __future__ import annotations

from pathlib import Path
import os
import sys

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import audit_k_day_all_pg as ka
import repair_month_all_pg as rm

DAY = "2026-10-08"
RID = "20261008_14_05"

def main():
    if os.geteuid() == 0:
        raise SystemExit("STOP: run as postgres")
    print("MODE=READ_ONLY_NONSTANDARD_RESULT_AUDIT", flush=True)
    with psycopg.connect(
        "postgresql:///railway",
        options="-c default_transaction_read_only=on -c statement_timeout=15000",
    ) as conn:
        with conn.cursor() as c:
            c.execute("SELECT race_id FROM public.v2_races WHERE race_id=%s", (RID,))
            races = c.fetchall()
            c.execute("SELECT lane,racer_number FROM public.v2_race_entries "
                      "WHERE race_id=%s ORDER BY lane", (RID,))
            roster = [(int(a), int(b)) for a,b in c.fetchall()]
            c.execute("SELECT race_id,result_status,trifecta_ticket,"
                      "trifecta_payout_yen,source FROM public.v2_results "
                      "WHERE race_id=%s", (RID,))
            results = c.fetchall()
            c.execute("SELECT "
                      "(SELECT count(*) FROM public.v2_results WHERE race_id >= '20261008_' AND race_id < '20261009_'),"
                      "(SELECT count(*) FROM public.v2_results WHERE race_id >= '20261015_' AND race_id < '20261016_'),"
                      "(SELECT count(*) FROM public.v2_results WHERE race_id >= '20261016_' AND race_id < '20261017_'),"
                      "(SELECT count(*) FROM public.v2_results WHERE race_id >= '20261017_' AND race_id < '20261018_')")
            day_counts = tuple(c.fetchone())
    print("RESULT_ROWS_BY_DAY_08_15_16_17=" + str(day_counts), flush=True)
    print(f"DB_RACES={len(races)} DB_ENTRIES={len(roster)} DB_RESULTS={len(results)}", flush=True)
    if day_counts != (143,156,156,168) or len(races) != 1 or len(roster) != 6 or results:
        raise RuntimeError("STOP: DB state differs from verified completed stage")
    if sorted(l for l,_ in roster) != list(range(1,7)):
        raise RuntimeError("STOP: DB roster has bad lanes")

    ka.TARGET_DATE = DAY
    text = ka.get_k_text(DAY)
    all_races = [r for section in ka.split_venue_sections(text.splitlines())
                 for r in ka.parse_section(section)]
    matches = [r for r in all_races if r["race_id"] == RID]
    if len(all_races) != 144 or len(matches) != 1:
        raise RuntimeError("STOP: official K count or race match differs")
    target = matches[0]
    k_roster = sorted((int(e["lane"]), int(e["racer_number"])) for e in target["entries"])
    if k_roster != sorted(roster) or target["parse_failed_candidate_lines"]:
        raise RuntimeError("STOP: official K vs DB roster mismatch")
    print("VENUE=" + str(target["venue_name"]) + " RACE_NO=5", flush=True)
    print("K_TICKET=" + str(target.get("trifecta_ticket")), flush=True)
    print("K_PAYOUT=" + str(target.get("trifecta_payout")), flush=True)
    print("K_FINISH_ORDER=" + str(target.get("finish_order")), flush=True)
    print("K_FINISH_STATUSES=" +
          str([(e["lane"], e.get("finish_status"), e.get("finish_position"))
               for e in sorted(target["entries"], key=lambda x: x["lane"])]), flush=True)

    url = rm._official_url("raceresult", DAY, "14", 5)
    html = rm._fetch(url)
    if not html or rm._looks_no_race(html):
        print("HTML_RESULT_UNAVAILABLE_OR_NO_RACE", flush=True)
        print("STOP: hold nonstandard result for separate manual review", flush=True)
        return
    official = rm.parse_result(html)
    print("HTML_RESULT_STATUS=" + str(official.get("result_status")), flush=True)
    print("HTML_RACE_STATUS=" + str(official.get("race_status")), flush=True)
    print("HTML_TICKET=" + str(official.get("trifecta_ticket")), flush=True)
    print("HTML_PAYOUT=" + str(official.get("trifecta_payout_yen")), flush=True)
    print("NONSTANDARD_AUDIT_COMPLETE_NO_DB_WRITES", flush=True)
    print("DO_NOT_INSERT_UNTIL_SPECIAL_HANDLING_APPROVED", flush=True)
    print("HISTORICAL_RETRIEVAL_NOT_PREDECISION", flush=True)

if __name__ == "__main__":
    main()
