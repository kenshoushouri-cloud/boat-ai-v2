# -*- coding: utf-8 -*-
"""Read-only official K vs ConoHa audit for existing-race missing results.

No insert, update, delete, DDL, cron, or model changes. Acquired historical
results must NOT be used as pre-deadline prediction evidence.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
import sys

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import audit_k_day_all_pg as ka

DB = "postgresql:///railway"
DAYS = [
    ("2026-10-08", 144, 144),
    ("2026-10-15", 156, 124),
    ("2026-10-16", 156, 21),
    ("2026-10-17", 168, 1),
]


def read_db(day):
    begin = day.replace("-", "") + "_"
    end = (date.fromisoformat(day) + timedelta(days=1)).strftime("%Y%m%d") + "_"
    with psycopg.connect(
        DB, options="-c default_transaction_read_only=on -c statement_timeout=15000"
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT race_id FROM public.v2_races WHERE race_id >= %s AND race_id < %s",
                        (begin, end))
            races = {r[0] for r in cur.fetchall()}
            cur.execute(
                "SELECT race_id,lane,racer_number FROM public.v2_race_entries "
                "WHERE race_id >= %s AND race_id < %s", (begin, end))
            entries = cur.fetchall()
            cur.execute(
                "SELECT race_id,trifecta_ticket,trifecta_payout_yen FROM public.v2_results "
                "WHERE race_id >= %s AND race_id < %s", (begin, end))
            results = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    return races, entries, results


def read_k(day):
    text = ka.get_k_text(day)
    sections = ka.split_venue_sections(text.splitlines())
    rows = [r for section in sections for r in ka.parse_section(section)]
    official = {}
    for r in rows:
        rid = r["race_id"]
        lanes = [e["lane"] for e in r["entries"]]
        if rid in official or sorted(lanes) != [1, 2, 3, 4, 5, 6] or r["parse_failed_candidate_lines"]:
            raise RuntimeError("STOP: K race duplicate, bad lane, or parse issue: " + rid)
        official[rid] = r
    return official


def audit(day, expected_races, expected_missing):
    official = read_k(day)
    race_ids, entry_rows, results = read_db(day)
    unexpected = sorted(race_ids ^ set(official))
    rosters = {}
    for rid, lane, racer in entry_rows:
        rosters.setdefault(rid, []).append((lane, racer))
    roster_bad = []
    for rid in race_ids:
        db = sorted(rosters.get(rid, []))
        k = sorted((e["lane"], e["racer_number"]) for e in official[rid]["entries"]) if rid in official else []
        if len(db) != 6 or db != k:
            roster_bad.append(rid)
    missing = sorted(race_ids - set(results))
    nonstandard = [rid for rid in missing if
                   not official[rid].get("trifecta_ticket") or
                   int(official[rid].get("trifecta_payout") or 0) <= 0] if not unexpected else []
    conflicts = []
    for rid, (ticket, payout) in results.items():
        if rid not in official:
            conflicts.append(rid)
            continue
        k = official[rid]
        if ((ticket is not None and ticket != k.get("trifecta_ticket")) or
            (payout is not None and int(payout) > 0 and
             int(payout) != int(k.get("trifecta_payout") or 0))):
            conflicts.append(rid)
    print(
        f"DAY={day} K={len(official)} RACES={len(race_ids)} "
        f"RESULTS={len(results)} MISSING={len(missing)} "
        f"ELIGIBLE={len(missing)-len(nonstandard)} NONSTANDARD={len(nonstandard)} "
        f"BAD_ROSTERS={len(roster_bad)} K_ID_DIFF={len(unexpected)} "
        f"EXISTING_RESULT_CONFLICT={len(conflicts)}", flush=True)
    if nonstandard:
        print("NONSTANDARD_SAMPLES=" + str(nonstandard[:5]), flush=True)
    if roster_bad or unexpected or conflicts:
        print("AUDIT_SAMPLES=" + str((roster_bad[:3], unexpected[:3], conflicts[:3])), flush=True)
    if (len(official) != expected_races or len(race_ids) != expected_races
        or len(missing) != expected_missing or roster_bad or unexpected or conflicts):
        raise RuntimeError("STOP: official K vs DB differs; do not write results")
    return len(missing), len(nonstandard)


def main():
    if os.geteuid() == 0:
        raise SystemExit("STOP: run as postgres, not root")
    print("MODE=READ_ONLY_RESULTS_PREFLIGHT", flush=True)
    total = blocked = 0
    for day, races, missing in DAYS:
        m, b = audit(day, races, missing)
        total += m
        blocked += b
    if total != 290:
        raise RuntimeError("STOP: expected 290 missing results")
    print(f"TOTAL_MISSING={total} SAFE_STANDARD={total-blocked} NONSTANDARD={blocked}", flush=True)
    print("READ_ONLY_RESULTS_PREFLIGHT_PASS_NO_DB_WRITES", flush=True)
    print("HISTORICAL_RETRIEVAL_NOT_PREDECISION", flush=True)


if __name__ == "__main__":
    main()
