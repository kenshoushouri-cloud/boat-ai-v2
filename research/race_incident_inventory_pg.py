# -*- coding: utf-8 -*-
"""Read-only inventory of abnormal result statuses for the frozen V5 research range."""
from __future__ import annotations

import os
from collections import defaultdict

import psycopg
from psycopg.rows import dict_row

START = os.getenv("INCIDENT_START_DATE", "2025-07-01")
END = os.getenv("INCIDENT_END_DATE", "2026-10-05")


def main() -> None:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is required")

    with psycopg.connect(url, row_factory=dict_row) as conn:
        cur = conn.cursor()
        cur.execute("BEGIN READ ONLY")

        cur.execute(
            """
            select count(*) as races
            from v2_races
            where race_date between %s and %s
            """,
            (START, END),
        )
        total_races = int(cur.fetchone()["races"])

        cur.execute(
            """
            select count(*) as rows, count(distinct e.race_id) as races
            from v2_result_entries e
            join v2_races r on r.race_id=e.race_id
            where r.race_date between %s and %s
            """,
            (START, END),
        )
        coverage = cur.fetchone()

        cur.execute(
            """
            select coalesce(nullif(trim(e.finish_status),''),'(blank)') as status,
                   count(*) as rows,
                   count(distinct e.race_id) as races
            from v2_result_entries e
            join v2_races r on r.race_id=e.race_id
            where r.race_date between %s and %s
            group by 1
            order by 1
            """,
            (START, END),
        )
        statuses = cur.fetchall()

        cur.execute(
            """
            select e.race_id,
                   coalesce(nullif(trim(e.finish_status),''),'') as status,
                   coalesce(e.is_flying,false) as is_flying,
                   coalesce(e.is_late,false) as is_late
            from v2_result_entries e
            join v2_races r on r.race_id=e.race_id
            where r.race_date between %s and %s
            """,
            (START, END),
        )
        rows = cur.fetchall()

        cur.execute(
            """
            select r.race_id, count(e.lane) as n
            from v2_races r
            left join v2_result_entries e on e.race_id=r.race_id
            where r.race_date between %s and %s
            group by r.race_id
            having count(e.lane) <> 6
            """,
            (START, END),
        )
        incomplete = cur.fetchall()

        cur.execute(
            """
            with per_race as (
              select r.race_id,
                     date_trunc('month', r.race_date)::date as month,
                     count(e.lane) as n
              from v2_races r
              left join v2_result_entries e on e.race_id=r.race_id
              where r.race_date between %s and %s
              group by r.race_id, date_trunc('month', r.race_date)::date
            )
            select month,
                   count(*) filter (where n <> 6) as incomplete_races,
                   count(*) filter (where n = 0) as n0,
                   count(*) filter (where n = 1) as n1,
                   count(*) filter (where n = 2) as n2,
                   count(*) filter (where n = 3) as n3,
                   count(*) filter (where n = 4) as n4,
                   count(*) filter (where n = 5) as n5,
                   count(*) filter (where n = 6) as n6,
                   count(*) as total_races
            from per_race
            group by month
            order by month
            """,
            (START, END),
        )
        monthly_incomplete = cur.fetchall()

        cur.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema='public' and table_name='v2_results'
            """
        )
        result_cols = {x["column_name"] for x in cur.fetchall()}

        whole_void = []
        if {"result_status", "race_status"} <= result_cols:
            cur.execute(
                """
                select v.race_id
                from v2_results v
                join v2_races r on r.race_id=v.race_id
                where r.race_date between %s and %s
                  and lower(coalesce(v.result_status,'')) in ('cancelled','canceled')
                  and lower(coalesce(v.race_status,'')) in ('cancelled','canceled')
                """,
                (START, END),
            )
            whole_void = cur.fetchall()

        conn.rollback()

    by_race: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        rid = str(row["race_id"])
        status = str(row["status"] or "").strip()

        if status in {"K0", "K1"} or status.startswith("欠"):
            by_race[rid].add("withdrawal")
        if status in {"L0", "L1"} or bool(row["is_late"]):
            by_race[rid].add("late")
        if status == "F" or bool(row["is_flying"]):
            by_race[rid].add("flying")
        if status in {"S0", "S1", "S2"} or any(
            token in status for token in ("失格", "妨", "転", "落", "沈")
        ):
            by_race[rid].add("incident_or_disqualification")
        if (
            status
            and not status.isdigit()
            and status not in {"K0", "K1", "L0", "L1", "F", "S0", "S1", "S2"}
        ):
            by_race[rid].add("other_nonstandard_status")

    categories: dict[str, set[str]] = defaultdict(set)
    for race_id, names in by_race.items():
        for name in names:
            categories[name].add(race_id)

    abnormal = set(by_race)
    result_races = int(coverage["races"])
    result_rows = int(coverage["rows"])

    print(f"INCIDENT_INVENTORY_RANGE={START}..{END}")
    print(f"TOTAL_RACES={total_races}")
    print(f"RESULT_ENTRY_ROWS={result_rows}")
    print(f"RESULT_ENTRY_RACES={result_races}")
    print(
        "RESULT_ENTRY_COVERAGE_PCT="
        f"{(100.0 * result_races / total_races if total_races else 0):.3f}"
    )
    print(f"INCOMPLETE_RESULT_ENTRY_RACES={len(incomplete)}")
    print("INCOMPLETE_MONTHLY_BEGIN")
    for row in monthly_incomplete:
        print(
            "MONTH "
            f"{row['month']} "
            f"incomplete={int(row['incomplete_races'])} "
            f"n0={int(row['n0'])} n1={int(row['n1'])} n2={int(row['n2'])} "
            f"n3={int(row['n3'])} n4={int(row['n4'])} n5={int(row['n5'])} "
            f"n6={int(row['n6'])} total={int(row['total_races'])}"
        )
    print("INCOMPLETE_MONTHLY_END")
    print(f"ABNORMAL_DISTINCT_RACES={len(abnormal)}")
    for name in (
        "withdrawal",
        "flying",
        "late",
        "incident_or_disqualification",
        "other_nonstandard_status",
    ):
        print(f"CATEGORY {name} races={len(categories[name])}")
    print(f"WHOLE_RACE_VOID={len(whole_void)}")
    print("STATUS_COUNTS_BEGIN")
    for row in statuses:
        print(
            f"STATUS {row['status']} "
            f"rows={int(row['rows'])} races={int(row['races'])}"
        )
    print("STATUS_COUNTS_END")
    print("INCIDENT_INVENTORY_READ_ONLY=PASS")


if __name__ == "__main__":
    main()
