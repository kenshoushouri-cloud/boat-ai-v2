# -*- coding: utf-8 -*-
"""Read-only readiness audit for racer x venue x course x condition features.

This audit measures data coverage, joinability, and sample density only.
It does not derive correction coefficients and never writes to PostgreSQL.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Iterable

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
START_DATE = date.fromisoformat(os.getenv("CONDITION_AUDIT_START_DATE", "2025-07-01"))
END_DATE = date.fromisoformat(os.getenv("CONDITION_AUDIT_END_DATE", "2026-08-22"))
HIST_LABEL = "historical"


def fetch_all(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def fetch_one(conn, query, params=()):
    rows = fetch_all(conn, query, params)
    return dict(rows[0]) if rows else {}


def columns(conn, table: str) -> list[str]:
    rows = fetch_all(
        conn,
        """select column_name from information_schema.columns
           where table_schema='public' and table_name=%s order by ordinal_position""",
        (table,),
    )
    return [str(r["column_name"]) for r in rows]


def table_exists(conn, table: str) -> bool:
    return bool(fetch_one(
        conn,
        """select exists(select 1 from information_schema.tables
           where table_schema='public' and table_name=%s) as ok""",
        (table,),
    ).get("ok"))


def pick(cols: Iterable[str], names: Iterable[str]) -> str | None:
    have = set(cols)
    return next((n for n in names if n in have), None)


def pct(n: int, d: int) -> float:
    return 0.0 if d == 0 else 100.0 * n / d


def print_density(label: str, row: dict) -> None:
    print(
        f"DENSITY_{label}=groups:{int(row.get('groups') or 0)} "
        f"median:{float(row.get('median_n') or 0):.1f} max:{int(row.get('max_n') or 0)} "
        f"ge20:{int(row.get('ge20') or 0)} ge50:{int(row.get('ge50') or 0)} "
        f"ge100:{int(row.get('ge100') or 0)}",
        flush=True,
    )


def density(conn, group_exprs: list[sql.Composed | sql.Identifier], base_from: sql.Composed, params: tuple, label: str) -> None:
    group_sql = sql.SQL(", ").join(group_exprs)
    q = sql.SQL("""
        with grouped as (
          select {groups}, count(*)::bigint as n
          {base_from}
          group by {groups}
        )
        select count(*)::bigint as groups,
               coalesce(percentile_cont(0.5) within group(order by n),0)::float8 as median_n,
               coalesce(max(n),0)::bigint as max_n,
               count(*) filter(where n>=20)::bigint as ge20,
               count(*) filter(where n>=50)::bigint as ge50,
               count(*) filter(where n>=100)::bigint as ge100
        from grouped
    """).format(groups=group_sql, base_from=base_from)
    print_density(label, fetch_one(conn, q, params))


def field_coverage(conn, table: str, fields: list[str]) -> None:
    cols = set(columns(conn, table))
    present = [f for f in fields if f in cols]
    expr = [sql.SQL("count(*)::bigint as total")]
    for f in present:
        expr.append(sql.SQL("count(*) filter(where {} is not null)::bigint as {}").format(sql.Identifier(f), sql.Identifier(f)))
    q = sql.SQL("select {} from {} where race_date >= %s and race_date <= %s and snapshot_label=%s").format(
        sql.SQL(", ").join(expr), sql.Identifier(table)
    )
    row = fetch_one(conn, q, (START_DATE, END_DATE, HIST_LABEL))
    total = int(row.get("total") or 0)
    prefix = "WEATHER" if "weather" in table else "EXHIBITION"
    print(f"{prefix}_TOTAL={total}", flush=True)
    for f in fields:
        if f not in cols:
            print(f"{prefix}_{f.upper()}=COLUMN_MISSING", flush=True)
        else:
            n = int(row.get(f) or 0)
            print(f"{prefix}_{f.upper()}={n}/{total} ({pct(n,total):.1f}%)", flush=True)


def condition_density(conn, racer_col: str, race_date_col: str, expression: str, label: str) -> None:
    q = sql.SQL("""
        with grouped as (
          select e.{racer}, {bucket} as bucket, count(*)::bigint as n
          from v2_race_entries e
          join v2_races r on r.race_id=e.race_id
          join v2_realtime_weather_snapshots w
            on w.race_id=e.race_id and w.snapshot_label=%s
          where r.{rdate} >= %s and r.{rdate} <= %s and e.{racer} is not null
          group by e.{racer}, bucket
        )
        select count(*)::bigint as groups,
               count(*) filter(where n>=20)::bigint as ge20,
               count(*) filter(where n>=50)::bigint as ge50,
               count(*) filter(where n>=100)::bigint as ge100
        from grouped
    """).format(
        racer=sql.Identifier(racer_col), rdate=sql.Identifier(race_date_col), bucket=sql.SQL(expression)
    )
    row = fetch_one(conn, q, (HIST_LABEL, START_DATE, END_DATE))
    print(
        f"CONDITION_DENSITY_{label}=groups:{int(row.get('groups') or 0)} "
        f"ge20:{int(row.get('ge20') or 0)} ge50:{int(row.get('ge50') or 0)} ge100:{int(row.get('ge100') or 0)}",
        flush=True,
    )


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    if END_DATE < START_DATE:
        raise RuntimeError("invalid audit period")

    print("CONDITION_AUDIT_MODE=read_only", flush=True)
    print(f"CONDITION_AUDIT_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("CONDITION_AUDIT_POLICY=no_coefficients_no_writes_no_line", flush=True)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        required = ["v2_races", "v2_race_entries", "v2_realtime_weather_snapshots", "v2_realtime_exhibition_snapshots"]
        missing = [t for t in required if not table_exists(conn, t)]
        print(f"SCHEMA_REQUIRED_MISSING={','.join(missing) or '-'}", flush=True)
        if missing:
            raise SystemExit(2)

        race_cols = columns(conn, "v2_races")
        entry_cols = columns(conn, "v2_race_entries")
        weather_cols = columns(conn, "v2_realtime_weather_snapshots")
        ex_cols = columns(conn, "v2_realtime_exhibition_snapshots")
        racer_col = pick(entry_cols, ["registration_number", "registration_no", "racer_id", "racer_no"])
        lane_col = pick(entry_cols, ["lane", "course", "boat_no"])
        venue_col = pick(race_cols, ["venue_id", "venue_code", "stadium_code", "place_code"])
        race_date_col = pick(race_cols, ["race_date", "target_date", "date"])
        print(f"SCHEMA_RACER_KEY={racer_col or 'MISSING'}", flush=True)
        print(f"SCHEMA_LANE_KEY={lane_col or 'MISSING'}", flush=True)
        print(f"SCHEMA_VENUE_KEY={venue_col or 'MISSING'}", flush=True)
        print(f"SCHEMA_RACE_DATE={race_date_col or 'MISSING'}", flush=True)
        if not all([racer_col, lane_col, venue_col, race_date_col]):
            raise SystemExit(3)

        field_coverage(conn, "v2_realtime_weather_snapshots", [
            "weather", "wind_speed_m", "wind_direction", "wave_height_cm", "temperature_c", "water_temperature_c"
        ])
        field_coverage(conn, "v2_realtime_exhibition_snapshots", [
            "exhibition_time", "exhibition_time_rank", "exhibition_time_diff", "start_timing", "start_timing_rank",
            "start_timing_diff", "exhibition_course", "tilt", "tilt_change"
        ])

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
            sql.SQL("select count(*)::bigint as n, count(distinct e.{racer})::bigint as racers ").format(racer=racer) + base_from,
            params,
        )
        print(f"PARTICIPANT_ROWS={int(p.get('n') or 0)}", flush=True)
        print(f"DISTINCT_RACERS={int(p.get('racers') or 0)}", flush=True)

        density(conn, [sql.SQL("e.") + racer], base_from, params, "RACER")
        density(conn, [sql.SQL("e.") + racer, sql.SQL("r.") + venue], base_from, params, "RACER_VENUE")
        density(conn, [sql.SQL("e.") + racer, sql.SQL("e.") + lane], base_from, params, "RACER_LANE")
        density(conn, [sql.SQL("e.") + racer, sql.SQL("r.") + venue, sql.SQL("e.") + lane], base_from, params, "RACER_VENUE_LANE")

        wh = set(weather_cols)
        if "wind_speed_m" in wh:
            condition_density(conn, racer_col, race_date_col, "case when w.wind_speed_m is null then 'missing' when w.wind_speed_m < 2 then '<2' when w.wind_speed_m < 4 then '2-<4' when w.wind_speed_m < 6 then '4-<6' else '6+' end", "WIND")
        if "wave_height_cm" in wh:
            condition_density(conn, racer_col, race_date_col, "case when w.wave_height_cm is null then 'missing' when w.wave_height_cm < 3 then '<3' when w.wave_height_cm < 6 then '3-<6' when w.wave_height_cm < 10 then '6-<10' else '10+' end", "WAVE")
        if "temperature_c" in wh:
            condition_density(conn, racer_col, race_date_col, "case when w.temperature_c is null then 'missing' when w.temperature_c < 10 then '<10' when w.temperature_c < 20 then '10-<20' when w.temperature_c < 30 then '20-<30' else '30+' end", "TEMP")
        if "water_temperature_c" in wh:
            condition_density(conn, racer_col, race_date_col, "case when w.water_temperature_c is null then 'missing' when w.water_temperature_c < 10 then '<10' when w.water_temperature_c < 20 then '10-<20' when w.water_temperature_c < 30 then '20-<30' else '30+' end", "WATER_TEMP")

        ex_lane = pick(ex_cols, ["lane", "course", "boat_no"])
        if ex_lane:
            q = sql.SQL("""
                select count(*)::bigint as participant_rows,
                       count(*) filter(where x.race_id is not null)::bigint as matched_rows
                from v2_race_entries e join v2_races r on r.race_id=e.race_id
                left join v2_realtime_exhibition_snapshots x
                  on x.race_id=e.race_id and x.{xlane}=e.{elane} and x.snapshot_label=%s
                where r.{rdate} >= %s and r.{rdate} <= %s
            """).format(xlane=sql.Identifier(ex_lane), elane=lane, rdate=rdate)
            j = fetch_one(conn, q, (HIST_LABEL, START_DATE, END_DATE))
            total = int(j.get("participant_rows") or 0)
            matched = int(j.get("matched_rows") or 0)
            print(f"EXHIBITION_JOINABLE={matched}/{total} ({pct(matched,total):.1f}%)", flush=True)
        else:
            print("EXHIBITION_JOINABLE=SCHEMA_UNRESOLVED", flush=True)

        if table_exists(conn, "v2_result_entries"):
            result_cols = columns(conn, "v2_result_entries")
            result_lane = pick(result_cols, ["lane", "course", "boat_no"])
            finish_col = pick(result_cols, ["finish_order", "finish", "rank", "arrival_order", "place"])
            if result_lane and finish_col:
                q = sql.SQL("""
                    select count(*)::bigint as participant_rows,
                           count(*) filter(where z.race_id is not null)::bigint as matched_rows,
                           count(*) filter(where z.{finish} is not null)::bigint as outcome_rows
                    from v2_race_entries e join v2_races r on r.race_id=e.race_id
                    left join v2_result_entries z on z.race_id=e.race_id and z.{zlane}=e.{elane}
                    where r.{rdate} >= %s and r.{rdate} <= %s
                """).format(finish=sql.Identifier(finish_col), zlane=sql.Identifier(result_lane), elane=lane, rdate=rdate)
                j = fetch_one(conn, q, params)
                total = int(j.get("participant_rows") or 0)
                matched = int(j.get("matched_rows") or 0)
                usable = int(j.get("outcome_rows") or 0)
                print(f"RESULT_JOINABLE={matched}/{total} ({pct(matched,total):.1f}%)", flush=True)
                print(f"RESULT_OUTCOME_USABLE={usable}/{total} ({pct(usable,total):.1f}%)", flush=True)
            else:
                print("RESULT_JOINABLE=SCHEMA_UNRESOLVED", flush=True)
        else:
            print("RESULT_JOINABLE=TABLE_MISSING", flush=True)

    print("TILT_POLICY=coverage_diagnostic_only_not_feature_ready", flush=True)
    print("CONDITION_AUDIT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
