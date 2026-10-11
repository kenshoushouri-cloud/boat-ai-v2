# -*- coding: utf-8 -*-
"""Lightweight read-only Opponent provenance coverage diagnostic.

Counts usable historical model_version=102 rows, timing-clean original Forward
model_version=2 rows, races with no Opponent row, and existing but unusable
rows. It never reads outcomes/odds/payouts and never writes the database.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
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
                       s.model_version,s.train_end,
                       s.matched_opponents,s.base_win,s.adj_win,
                       s.created_at,s.updated_at
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
    days: dict[str, Counter[str]] = defaultdict(Counter)
    missing_ids: list[str] = []
    invalid_ids: list[str] = []

    for row in rows:
        day = str(row["race_date"])[:10]
        totals["races"] += 1
        days[day]["races"] += 1

        has_row = row.get("model_version") is not None
        if not has_row:
            totals["no_row"] += 1
            days[day]["no_row"] += 1
            missing_ids.append(str(row["race_id"]))
            continue

        provenance = opponent_provenance(row)
        if provenance == "historical102":
            totals["historical102"] += 1
            totals["usable"] += 1
            days[day]["historical102"] += 1
            days[day]["usable"] += 1
        elif provenance == "forward_v2_timing_clean":
            totals["forward_v2_timing_clean"] += 1
            totals["usable"] += 1
            days[day]["forward_v2_timing_clean"] += 1
            days[day]["usable"] += 1
        else:
            totals["invalid_existing"] += 1
            days[day]["invalid_existing"] += 1
            invalid_ids.append(str(row["race_id"]))

    races = int(totals["races"])
    usable = int(totals["usable"])
    payload = {
        "contract": "OPPONENT_PROVENANCE_GAP_READONLY_V1",
        "period": [start_date, end_date],
        "totals": {
            "races": races,
            "usable": usable,
            "usable_pct": round(100.0 * usable / races, 2) if races else 0.0,
            "historical102": int(totals["historical102"]),
            "forward_v2_timing_clean": int(totals["forward_v2_timing_clean"]),
            "no_row": int(totals["no_row"]),
            "invalid_existing": int(totals["invalid_existing"]),
            "safe_fill_missing_only_candidates": int(totals["no_row"]),
        },
        "days": [
            {
                "date": day,
                "races": int(c["races"]),
                "usable": int(c["usable"]),
                "historical102": int(c["historical102"]),
                "forward_v2_timing_clean": int(c["forward_v2_timing_clean"]),
                "no_row": int(c["no_row"]),
                "invalid_existing": int(c["invalid_existing"]),
            }
            for day, c in sorted(days.items())
        ],
        "missing_race_ids": missing_ids,
        "invalid_existing_race_ids": invalid_ids,
        "safety": {
            "transaction_read_only": True,
            "result_read": False,
            "odds_read": False,
            "payout_read": False,
            "db_write": False,
            "production_change": False,
            "purchase_action": False,
        },
    }
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", required=True)
    ap.add_argument("--end-date", required=True)
    ap.add_argument("--output", default="opponent-gap.json")
    args = ap.parse_args()

    out = audit(args.start_date, args.end_date)
    Path(args.output).write_text(
        json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("OPP_PROVENANCE_TOTALS=" + json.dumps(out["totals"], sort_keys=True), flush=True)
    print(
        "OPP_PROVENANCE_GAP_DAYS="
        + json.dumps(
            [x for x in out["days"] if x["no_row"] or x["invalid_existing"]],
            sort_keys=True,
        ),
        flush=True,
    )
    print("OPP_PROVENANCE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
