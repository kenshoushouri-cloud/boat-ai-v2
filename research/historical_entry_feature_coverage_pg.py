# -*- coding: utf-8 -*-
"""Read-only monthly coverage report for historical entry features."""
from __future__ import annotations

import argparse
import json
import os

import psycopg
from psycopg.rows import dict_row

FIELDS = (
    "f_count",
    "l_count",
    "avg_st",
    "national_win_rate",
    "national_place2_rate",
    "local_win_rate",
    "local_place2_rate",
    "motor_place2_rate",
    "boat_place2_rate",
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default=os.getenv("HIST_START_DATE"))
    ap.add_argument("--end-date", default=os.getenv("HIST_END_DATE"))
    args = ap.parse_args()
    if not args.start_date or not args.end_date:
        raise SystemExit("start/end date required")
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise SystemExit("DATABASE_URL required")

    select_counts = ",\n".join(
        f"count(e.{field}) as {field}_n" for field in FIELDS
    )
    sql = f"""
        select to_char(date_trunc('month',r.race_date),'YYYY-MM') as month,
               count(*) as entry_rows,
               {select_counts}
          from v2_race_entries e
          join v2_races r on r.race_id=e.race_id
         where r.race_date between %s and %s
         group by 1
         order by 1
    """

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute(sql, (args.start_date, args.end_date))
            rows = [dict(x) for x in cur.fetchall()]
        conn.rollback()

    for row in rows:
        total = int(row["entry_rows"])
        coverage = {}
        for field in FIELDS:
            n = int(row.get(f"{field}_n") or 0)
            coverage[field] = {
                "present": n,
                "coverage_pct": round((n / total * 100.0) if total else 0.0, 3),
            }
        row["coverage"] = coverage
        for field in FIELDS:
            row.pop(f"{field}_n", None)

    payload = {
        "contract": "HISTORICAL_ENTRY_FEATURE_COVERAGE_V1",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "read_only": True,
        "months": rows,
    }
    print("HIST_ENTRY_COVERAGE=" + json.dumps(payload, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
