# -*- coding: utf-8 -*-
"""Read-only audit for motor maturity/source readiness.

Purpose:
- Do NOT treat DB first-seen date as official motor use-start date.
- Discover whether any existing DB table/column already stores official motor use-start,
  replacement, cycle, or parts-change metadata.
- Measure how much of the historical motor population is left-censored by the
  2025-07-01 project data boundary.
- Identify venue/date bursts of first-observed motor numbers as diagnostics only.

No DB writes, no prediction changes, no Shadow changes, no LINE operations.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
START_DATE = date.fromisoformat(os.getenv("MOTOR_MATURITY_AUDIT_START_DATE", "2025-07-01"))
END_DATE = date.fromisoformat(os.getenv("MOTOR_MATURITY_AUDIT_END_DATE", "2026-08-22"))
LEFT_CENSOR_DAYS = int(os.getenv("MOTOR_MATURITY_LEFT_CENSOR_DAYS", "14"))


def rows(conn, q, p=()):
    with conn.cursor() as cur:
        cur.execute(q, p)
        return [dict(r) for r in cur.fetchall()]


def one(conn, q, p=()):
    xs = rows(conn, q, p)
    return xs[0] if xs else {}


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")

    print("MOTOR_MATURITY_MODE=read_only", flush=True)
    print(f"MOTOR_MATURITY_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("MOTOR_MATURITY_POLICY=official_start_preferred_db_first_seen_diagnostic_only", flush=True)
    print("MOTOR_MATURITY_NO_WRITES=1", flush=True)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather = 0")
            cur.execute("set work_mem = '8MB'")
            cur.execute("set statement_timeout = '120s'")

        schema = rows(
            conn,
            """
            select table_name,column_name,data_type
            from information_schema.columns
            where table_schema='public'
              and (
                lower(column_name) like '%motor%'
                or lower(column_name) like '%engine%'
                or lower(column_name) like '%parts%'
                or lower(column_name) like '%replace%'
                or lower(column_name) like '%exchange%'
                or lower(column_name) like '%start_date%'
                or lower(column_name) like '%use_start%'
              )
            order by table_name,column_name
            """,
        )
        print(f"MOTOR_METADATA_SCHEMA_COLUMNS={len(schema)}", flush=True)
        for r in schema[:120]:
            print(
                f"MOTOR_METADATA_COLUMN={r['table_name']}.{r['column_name']}:{r['data_type']}",
                flush=True,
            )

        ecols = {r['column_name'] for r in rows(
            conn,
            "select column_name from information_schema.columns where table_schema='public' and table_name='v2_race_entries'",
        )}
        required = {'race_id','motor_no','motor_place2_rate'}
        missing = sorted(required - ecols)
        if missing:
            print(f"MOTOR_MATURITY_SCHEMA_FAIL={missing}", flush=True)
            raise SystemExit(2)
        print("MOTOR_MATURITY_SCHEMA=PASS", flush=True)

        stats = one(
            conn,
            """
            with x as (
              select coalesce(r.venue_id,r.venue_code) as venue_id,
                     e.motor_no::text motor_no,
                     min(r.race_date)::date first_seen,
                     max(r.race_date)::date last_seen,
                     count(distinct e.race_id)::bigint appearances,
                     count(*) filter(where e.motor_place2_rate between 0 and 100)::bigint rate_rows
              from v2_race_entries e
              join v2_races r on r.race_id=e.race_id
              where r.race_date between %s and %s
                and e.motor_no is not null
              group by 1,2
            )
            select count(*)::bigint units,
                   count(*) filter(where first_seen <= %s)::bigint left_censored_units,
                   count(*) filter(where first_seen > %s)::bigint post_boundary_units,
                   count(*) filter(where appearances >= 10)::bigint ge10,
                   count(*) filter(where appearances >= 30)::bigint ge30,
                   count(*) filter(where appearances >= 60)::bigint ge60,
                   percentile_cont(0.5) within group(order by appearances)::float8 median_appearances,
                   max(appearances)::bigint max_appearances
            from x
            """,
            (
                START_DATE,
                END_DATE,
                START_DATE + timedelta(days=LEFT_CENSOR_DAYS),
                START_DATE + timedelta(days=LEFT_CENSOR_DAYS),
            ),
        )
        total = int(stats.get('units') or 0)
        left = int(stats.get('left_censored_units') or 0)
        post = int(stats.get('post_boundary_units') or 0)
        pct_left = 0.0 if total == 0 else left * 100.0 / total
        print(f"MOTOR_UNITS={total}", flush=True)
        print(f"MOTOR_LEFT_CENSORED_UNITS={left}/{total} ({pct_left:.1f}%)", flush=True)
        print(f"MOTOR_POST_BOUNDARY_UNITS={post}/{total}", flush=True)
        print(
            "MOTOR_APPEARANCE_DENSITY="
            f"median:{float(stats.get('median_appearances') or 0):.1f} "
            f"max:{int(stats.get('max_appearances') or 0)} "
            f"ge10:{int(stats.get('ge10') or 0)} ge30:{int(stats.get('ge30') or 0)} ge60:{int(stats.get('ge60') or 0)}",
            flush=True,
        )

        bursts = rows(
            conn,
            """
            with firsts as (
              select coalesce(r.venue_id,r.venue_code) as venue_id,
                     e.motor_no::text motor_no,
                     min(r.race_date)::date first_seen
              from v2_race_entries e
              join v2_races r on r.race_id=e.race_id
              where r.race_date between %s and %s and e.motor_no is not null
              group by 1,2
            ), b as (
              select venue_id,first_seen,count(*)::bigint new_motor_nos
              from firsts
              group by 1,2
            )
            select venue_id,first_seen,new_motor_nos
            from b
            where new_motor_nos >= 10
            order by new_motor_nos desc,first_seen,venue_id
            limit 80
            """,
            (START_DATE, END_DATE),
        )
        print(f"MOTOR_FIRST_SEEN_BURSTS={len(bursts)}", flush=True)
        for r in bursts:
            print(
                f"MOTOR_BURST=venue:{str(r['venue_id']).zfill(2)} date:{r['first_seen']} new_numbers:{int(r['new_motor_nos'])}",
                flush=True,
            )

        # Source readiness gate: DB first-seen is explicitly not enough for maturity.
        official_like = [
            r for r in schema
            if any(k in str(r['column_name']).lower() for k in ('use_start','start_date','replace','exchange'))
            and ('motor' in str(r['column_name']).lower() or 'motor' in str(r['table_name']).lower())
        ]
        print(f"MOTOR_OFFICIAL_START_LIKE_COLUMNS={len(official_like)}", flush=True)
        if official_like:
            for r in official_like[:40]:
                print(f"MOTOR_START_SOURCE_CANDIDATE={r['table_name']}.{r['column_name']}", flush=True)
        else:
            print("MOTOR_START_SOURCE_CANDIDATE=NONE_IN_CURRENT_DB", flush=True)

    print("MOTOR_MATURITY_RESULT=PASS_READ_ONLY", flush=True)
    print("MOTOR_MATURITY_NEXT=collect_official_use_start_before_any_maturity_weight", flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace('\n',' ').replace('\r',' ')[:700]
        print(f"MOTOR_MATURITY_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
