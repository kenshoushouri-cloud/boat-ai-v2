# -*- coding: utf-8 -*-
"""Lightweight result-blind Opponent provenance readiness diagnostic."""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research.historical_matched_contract_readiness_pg import opponent_provenance


def audit(start_date: str, end_date: str) -> dict[str, Any]:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute(
                """
                select r.race_id,r.race_date,r.deadline_at,
                       s.model_version,s.train_end,s.matched_opponents,
                       s.base_win,s.adj_win,s.created_at,s.updated_at
                  from v2_races r
                  left join v2_opponent_pressure_shadow_v2 s
                    on s.race_id=r.race_id
                 where r.race_date between %s and %s
                 order by r.race_date,r.race_id
                """,
                (start_date, end_date),
            )
            rows = [dict(x) for x in cur.fetchall()]
        conn.rollback()

    totals: Counter[str] = Counter()
    by_day: dict[str, Counter[str]] = defaultdict(Counter)
    no_row_dates: list[str] = []
    invalid_dates: list[str] = []

    for row in rows:
        day = str(row["race_date"])[:10]
        totals["races"] += 1
        by_day[day]["races"] += 1

        if row.get("model_version") is None:
            totals["no_row"] += 1
            by_day[day]["no_row"] += 1
            no_row_dates.append(day)
            continue

        provenance = opponent_provenance(row)
        if provenance == "historical102":
            totals["historical102"] += 1
            by_day[day]["historical102"] += 1
        elif provenance == "forward_v2_timing_clean":
            totals["forward_v2_timing_clean"] += 1
            by_day[day]["forward_v2_timing_clean"] += 1
        else:
            totals["invalid_existing"] += 1
            by_day[day]["invalid_existing"] += 1
            invalid_dates.append(day)

    totals["usable"] = totals["historical102"] + totals["forward_v2_timing_clean"]
    totals["unusable"] = totals["no_row"] + totals["invalid_existing"]
    totals["usable_pct"] = round(100.0 * totals["usable"] / totals["races"], 2) if totals["races"] else 0.0

    days = []
    for day in sorted(by_day):
        x = by_day[day]
        x["usable"] = x["historical102"] + x["forward_v2_timing_clean"]
        x["unusable"] = x["no_row"] + x["invalid_existing"]
        days.append({"date": day, **dict(x)})

    return {
        "contract": "OPPONENT_PROVENANCE_READINESS_V1",
        "period": [start_date, end_date],
        "totals": dict(totals),
        "days": days,
        "fill_missing_only": {
            "eligible_no_row_races": int(totals["no_row"]),
            "dates": sorted(set(no_row_dates)),
            "invalid_existing_races_not_safe_to_overwrite": int(totals["invalid_existing"]),
            "invalid_existing_dates": sorted(set(invalid_dates)),
        },
        "safety": {
            "transaction_read_only": True,
            "outcome_read": False,
            "odds_read": False,
            "payout_read": False,
            "db_write": False,
            "production_change": False,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", required=True)
    ap.add_argument("--end-date", required=True)
    ap.add_argument("--output", default="opponent-provenance-readiness.json")
    args = ap.parse_args()

    payload = audit(args.start_date, args.end_date)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    print("OPP_PROV_TOTALS=" + json.dumps(payload["totals"], sort_keys=True), flush=True)
    print(
        "OPP_PROV_FILL_MISSING_ONLY="
        + json.dumps(payload["fill_missing_only"], sort_keys=True),
        flush=True,
    )
    for row in payload["days"]:
        if int(row.get("unusable") or 0) > 0:
            print("OPP_PROV_GAP_DAY=" + json.dumps(row, sort_keys=True), flush=True)
    print("OPP_PROV_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
