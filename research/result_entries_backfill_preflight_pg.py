# -*- coding: utf-8 -*-
"""Read-only preflight for v2_result_entries K-file backfill."""
from __future__ import annotations

import os
import psycopg
from psycopg.rows import dict_row

START=os.getenv("K_START_DATE","2026-08-01")
END=os.getenv("K_END_DATE","2026-10-05")

def main():
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise SystemExit("DATABASE_URL required")

    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
        cur=conn.cursor()
        cur.execute("BEGIN READ ONLY")

        cur.execute("""
          with per_race as (
            select r.race_date, r.race_id, count(e.lane) as n
            from v2_races r
            left join v2_result_entries e on e.race_id=r.race_id
            where r.race_date between %s and %s
            group by r.race_date,r.race_id
          )
          select
            count(*) as total_races,
            count(*) filter (where n=6) as complete_races,
            count(*) filter (where n=0) as missing_races,
            count(*) filter (where n not in (0,6)) as partial_races,
            count(distinct race_date) filter (where n=0) as days_with_missing
          from per_race
        """,(START,END))
        s=cur.fetchone()

        cur.execute("""
          with per_race as (
            select r.race_date, r.race_id, count(e.lane) as n
            from v2_races r
            left join v2_result_entries e on e.race_id=r.race_id
            where r.race_date between %s and %s
            group by r.race_date,r.race_id
          )
          select race_date,
                 count(*) filter (where n=0) as missing_races,
                 count(*) filter (where n=6) as complete_races,
                 count(*) as total_races
          from per_race
          group by race_date
          having count(*) filter (where n=0) > 0
          order by race_date
        """,(START,END))
        days=cur.fetchall()

        cur.execute("select count(*) as n from v2_result_entries")
        row_count=int(cur.fetchone()["n"])

        cur.execute("""
          select pg_total_relation_size('v2_result_entries')::bigint as total_bytes
        """)
        total_bytes=int(cur.fetchone()["total_bytes"])

        conn.rollback()

    missing_races=int(s["missing_races"])
    expected_rows=missing_races*6
    avg_bytes=(total_bytes/row_count) if row_count else 0
    est_bytes=int(avg_bytes*expected_rows)
    est_mb=est_bytes/1024/1024

    print(f"K_PREFLIGHT_RANGE={START}..{END}")
    print(f"TOTAL_RACES={int(s['total_races'])}")
    print(f"COMPLETE_RACES={int(s['complete_races'])}")
    print(f"MISSING_RACES={missing_races}")
    print(f"PARTIAL_RACES={int(s['partial_races'])}")
    print(f"DAYS_WITH_MISSING={int(s['days_with_missing'])}")
    print(f"EXPECTED_NEW_ROWS_MAX={expected_rows}")
    print(f"CURRENT_RESULT_ENTRY_ROWS={row_count}")
    print(f"CURRENT_RESULT_ENTRY_TOTAL_BYTES={total_bytes}")
    print(f"AVG_BYTES_PER_RESULT_ENTRY_APPROX={avg_bytes:.1f}")
    print(f"ESTIMATED_ADDED_MB_APPROX={est_mb:.2f}")
    print("MISSING_DAYS_BEGIN")
    for d in days:
        print(
            f"DAY {d['race_date']} missing={int(d['missing_races'])} "
            f"complete={int(d['complete_races'])} total={int(d['total_races'])}"
        )
    print("MISSING_DAYS_END")
    print("DB_TRANSACTION=READ_ONLY")
    print("K_PREFLIGHT_RESULT=PASS")

if __name__=="__main__":
    main()
