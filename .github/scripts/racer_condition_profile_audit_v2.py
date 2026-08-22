# -*- coding: utf-8 -*-
"""Read-only corrected density audit for racer x venue x lane x condition.

This v2 audit fixes the racer-key selection used by the first readiness audit.
It never writes to PostgreSQL and derives no correction coefficients.
"""
from __future__ import annotations

import os
from datetime import date

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
START_DATE = date.fromisoformat(os.getenv("CONDITION_AUDIT_START_DATE", "2025-07-01"))
END_DATE = date.fromisoformat(os.getenv("CONDITION_AUDIT_END_DATE", "2026-08-22"))
HIST_LABEL = "historical"


def fetch_one(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row or {})


def columns(conn, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """select column_name from information_schema.columns
               where table_schema='public' and table_name=%s order by ordinal_position""",
            (table,),
        )
        return [str(r["column_name"]) for r in cur.fetchall()]


def pick(cols: list[str], names: list[str]) -> str | None:
    have = set(cols)
    return next((n for n in names if n in have), None)


def density(conn, groups: list[sql.Composed], base_from: sql.Composed, params: tuple, label: str) -> None:
    group_sql = sql.SQL(", ").join(groups)
    q = sql.SQL("""
        with grouped as (
          select {groups}, count(*)::bigint n
          {base_from}
          group by {groups}
        )
        select count(*)::bigint groups,
               coalesce(percentile_cont(0.5) within group(order by n),0)::float8 median_n,
               coalesce(max(n),0)::bigint max_n,
               count(*) filter(where n>=20)::bigint ge20,
               count(*) filter(where n>=50)::bigint ge50,
               count(*) filter(where n>=100)::bigint ge100
        from grouped
    """).format(groups=group_sql, base_from=base_from)
    r = fetch_one(conn, q, params)
    print(
        f"DENSITY_{label}=groups:{int(r.get('groups') or 0)} "
        f"median:{float(r.get('median_n') or 0):.1f} max:{int(r.get('max_n') or 0)} "
        f"ge20:{int(r.get('ge20') or 0)} ge50:{int(r.get('ge50') or 0)} ge100:{int(r.get('ge100') or 0)}",
        flush=True,
    )


def condition_density(conn, racer_col: str, race_date_col: str, expression: str, label: str) -> None:
    q = sql.SQL("""
        with grouped as (
          select e.{racer}, {bucket} bucket, count(*)::bigint n
          from v2_race_entries e
          join v2_races r on r.race_id=e.race_id
          join v2_realtime_weather_snapshots w
            on w.race_id=e.race_id and w.snapshot_label=%s
          where r.{rdate} >= %s and r.{rdate} <= %s and e.{racer} is not null
          group by e.{racer}, bucket
        )
        select count(*)::bigint groups,
               count(*) filter(where n>=20)::bigint ge20,
               count(*) filter(where n>=50)::bigint ge50,
               count(*) filter(where n>=100)::bigint ge100
        from grouped
    """).format(
        racer=sql.Identifier(racer_col),
        rdate=sql.Identifier(race_date_col),
        bucket=sql.SQL(expression),
    )
    r = fetch_one(conn, q, (HIST_LABEL, START_DATE, END_DATE))
    print(
        f"CONDITION_DENSITY_{label}=groups:{int(r.get('groups') or 0)} "
        f"ge20:{int(r.get('ge20') or 0)} ge50:{int(r.get('ge50') or 0)} ge100:{int(r.get('ge100') or 0)}",
        flush=True,
    )


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")

    print("CONDITION_AUDIT_V2_MODE=read_only", flush=True)
    print(f"CONDITION_AUDIT_V2_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("CONDITION_AUDIT_V2_POLICY=no_coefficients_no_writes_no_line", flush=True)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        ec = columns(conn, "v2_race_entries")
        rc = columns(conn, "v2_races")
        wc = set(columns(conn, "v2_realtime_weather_snapshots"))
        xc = columns(conn, "v2_realtime_exhibition_snapshots")

        racer_col = pick(ec, ["racer_number", "registration_number", "registration_no", "racer_id", "racer_no"])
        lane_col = pick(ec, ["lane", "course", "boat_no"])
        venue_col = pick(rc, ["venue_id", "venue_code", "stadium_code", "place_code"])
        race_date_col = pick(rc, ["race_date", "target_date", "date"])
        ex_lane = pick(xc, ["lane", "course", "boat_no"])

        print(f"SCHEMA_V2_RACER_KEY={racer_col or 'MISSING'}", flush=True)
        print(f"SCHEMA_V2_LANE_KEY={lane_col or 'MISSING'}", flush=True)
        print(f"SCHEMA_V2_VENUE_KEY={venue_col or 'MISSING'}", flush=True)
        print(f"SCHEMA_V2_RACE_DATE={race_date_col or 'MISSING'}", flush=True)
        if not all([racer_col, lane_col, venue_col, race_date_col, ex_lane]):
            print("CONDITION_AUDIT_V2_RESULT=FAIL_SCHEMA", flush=True)
            raise SystemExit(2)

        racer = sql.Identifier(racer_col)
        lane = sql.Identifier(lane_col)
        venue = sql.Identifier(venue_col)
        rdate = sql.Identifier(race_date_col)
        base_from = sql.SQL("""
            from v2_race_entries e join v2_races r on r.race_id=e.race_id
            where r.{rdate} >= %s and r.{rdate} <= %s and e.{racer} is not null
        """).format(rdate=rdate, racer=racer)
        params = (START_DATE, END_DATE)

        p = fetch_one(
            conn,
            sql.SQL("select count(*)::bigint n, count(distinct e.{racer})::bigint racers ").format(racer=racer) + base_from,
            params,
        )
        participant_rows = int(p.get("n") or 0)
        distinct_racers = int(p.get("racers") or 0)
        print(f"PARTICIPANT_V2_ROWS={participant_rows}", flush=True)
        print(f"DISTINCT_V2_RACERS={distinct_racers}", flush=True)
        if participant_rows == 0 or distinct_racers == 0:
            print("CONDITION_AUDIT_V2_RESULT=FAIL_ZERO_PARTICIPANTS", flush=True)
            raise SystemExit(3)

        density(conn, [sql.SQL("e.") + racer], base_from, params, "V2_RACER")
        density(conn, [sql.SQL("e.") + racer, sql.SQL("r.") + venue], base_from, params, "V2_RACER_VENUE")
        density(conn, [sql.SQL("e.") + racer, sql.SQL("e.") + lane], base_from, params, "V2_RACER_LANE")
        density(conn, [sql.SQL("e.") + racer, sql.SQL("r.") + venue, sql.SQL("e.") + lane], base_from, params, "V2_RACER_VENUE_LANE")

        if "wind_speed_m" in wc:
            condition_density(conn, racer_col, race_date_col, "case when w.wind_speed_m is null then 'missing' when w.wind_speed_m < 2 then '<2' when w.wind_speed_m < 4 then '2-<4' when w.wind_speed_m < 6 then '4-<6' else '6+' end", "V2_WIND")
        if "wave_height_cm" in wc:
            condition_density(conn, racer_col, race_date_col, "case when w.wave_height_cm is null then 'missing' when w.wave_height_cm < 3 then '<3' when w.wave_height_cm < 6 then '3-<6' when w.wave_height_cm < 10 then '6-<10' else '10+' end", "V2_WAVE")
        if "temperature_c" in wc:
            condition_density(conn, racer_col, race_date_col, "case when w.temperature_c is null then 'missing' when w.temperature_c < 10 then '<10' when w.temperature_c < 20 then '10-<20' when w.temperature_c < 30 then '20-<30' else '30+' end", "V2_TEMP")
        if "water_temperature_c" in wc:
            condition_density(conn, racer_col, race_date_col, "case when w.water_temperature_c is null then 'missing' when w.water_temperature_c < 10 then '<10' when w.water_temperature_c < 20 then '10-<20' when w.water_temperature_c < 30 then '20-<30' else '30+' end", "V2_WATER_TEMP")

        q = sql.SQL("""
            select count(*)::bigint participant_rows,
                   count(*) filter(where x.race_id is not null)::bigint matched_rows
            from v2_race_entries e join v2_races r on r.race_id=e.race_id
            left join v2_realtime_exhibition_snapshots x
              on x.race_id=e.race_id and x.{xlane}=e.{elane} and x.snapshot_label=%s
            where r.{rdate} >= %s and r.{rdate} <= %s
        """).format(xlane=sql.Identifier(ex_lane), elane=lane, rdate=rdate)
        j = fetch_one(conn, q, (HIST_LABEL, START_DATE, END_DATE))
        total = int(j.get("participant_rows") or 0)
        matched = int(j.get("matched_rows") or 0)
        print(f"EXHIBITION_V2_JOIN={matched}/{total} ({0.0 if total == 0 else 100.0*matched/total:.1f}%)", flush=True)

    print("TILT_V2_POLICY=coverage_diagnostic_only_not_feature_ready", flush=True)
    print("CONDITION_AUDIT_V2_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
