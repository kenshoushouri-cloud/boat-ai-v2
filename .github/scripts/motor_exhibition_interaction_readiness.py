# -*- coding: utf-8 -*-
"""Read-only readiness audit for motor/boat x exhibition x weather interactions.

No coefficients, DB writes, prediction changes, Shadow changes, Railway setting changes,
or LINE operations. Tilt is coverage-diagnostic only.
"""
from __future__ import annotations

import os
from datetime import date

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
START_DATE = date.fromisoformat(os.getenv("INTERACTION_AUDIT_START_DATE", "2025-07-01"))
END_DATE = date.fromisoformat(os.getenv("INTERACTION_AUDIT_END_DATE", "2026-08-22"))
HIST_LABEL = "historical"


def one(conn, q, p=()):
    with conn.cursor() as cur:
        cur.execute(q, p)
        return dict(cur.fetchone() or {})


def columns(conn, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "select column_name from information_schema.columns where table_schema='public' and table_name=%s",
            (table,),
        )
        return {str(r["column_name"]) for r in cur.fetchall()}


def density(conn, exprs: str, label: str, extra_where: str = "true") -> None:
    q = f"""
      with g as (
        select {exprs}, count(*)::bigint n
        from v2_race_entries e
        join v2_races r on r.race_id=e.race_id
        join v2_result_entries re on re.race_id=e.race_id and re.lane=e.lane
        left join v2_realtime_exhibition_snapshots x
          on x.race_id=e.race_id and x.lane=e.lane and x.snapshot_label=%s
        left join v2_realtime_weather_snapshots w
          on w.race_id=e.race_id and w.snapshot_label=%s
        where r.race_date between %s and %s
          and re.finish_position between 1 and 6
          and {extra_where}
        group by {exprs}
      )
      select count(*)::bigint groups,
             coalesce(percentile_cont(0.5) within group(order by n),0)::float8 median_n,
             coalesce(max(n),0)::bigint max_n,
             count(*) filter(where n>=20)::bigint ge20,
             count(*) filter(where n>=50)::bigint ge50,
             count(*) filter(where n>=100)::bigint ge100
      from g
    """
    r = one(conn, q, (HIST_LABEL, HIST_LABEL, START_DATE, END_DATE))
    print(
        f"DENSITY_{label}=groups:{int(r.get('groups') or 0)} median:{float(r.get('median_n') or 0):.1f} "
        f"max:{int(r.get('max_n') or 0)} ge20:{int(r.get('ge20') or 0)} "
        f"ge50:{int(r.get('ge50') or 0)} ge100:{int(r.get('ge100') or 0)}",
        flush=True,
    )


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")

    print("INTERACTION_READINESS_MODE=read_only", flush=True)
    print(f"INTERACTION_READINESS_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("INTERACTION_READINESS_POLICY=no_coefficients_no_writes_no_line", flush=True)
    print("TILT_POLICY=coverage_diagnostic_only_not_feature_ready", flush=True)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        ec = columns(conn, "v2_race_entries")
        xc = columns(conn, "v2_realtime_exhibition_snapshots")
        wc = columns(conn, "v2_realtime_weather_snapshots")
        rec = columns(conn, "v2_result_entries")
        rc = columns(conn, "v2_races")

        need = {
            "v2_race_entries": {"race_id", "lane", "motor_place2_rate", "boat_place2_rate"} - ec,
            "v2_realtime_exhibition_snapshots": {"race_id", "lane", "snapshot_label", "exhibition_time", "exhibition_time_rank", "start_timing", "start_timing_rank", "tilt"} - xc,
            "v2_realtime_weather_snapshots": {"race_id", "snapshot_label", "wind_speed_m", "wave_height_cm"} - wc,
            "v2_result_entries": {"race_id", "lane", "finish_position"} - rec,
            "v2_races": {"race_id", "race_date", "venue_id"} - rc,
        }
        bad = {k: sorted(v) for k, v in need.items() if v}
        if bad:
            print(f"INTERACTION_READINESS_SCHEMA_FAIL={bad}", flush=True)
            raise SystemExit(2)
        print("INTERACTION_READINESS_SCHEMA=PASS", flush=True)

        q = """
          select count(*)::bigint rows,
                 count(*) filter(where e.motor_place2_rate between 0 and 100)::bigint motor2,
                 count(*) filter(where e.boat_place2_rate between 0 and 100)::bigint boat2,
                 count(*) filter(where x.exhibition_time is not null)::bigint extime,
                 count(*) filter(where x.exhibition_time_rank between 1 and 6)::bigint exrank,
                 count(*) filter(where x.start_timing is not null)::bigint exst,
                 count(*) filter(where x.start_timing_rank between 1 and 6)::bigint exstrank,
                 count(*) filter(where x.tilt is not null)::bigint tilt,
                 count(*) filter(where w.wind_speed_m is not null)::bigint wind,
                 count(*) filter(where w.wave_height_cm is not null)::bigint wave,
                 count(*) filter(where e.motor_place2_rate between 0 and 100 and x.exhibition_time_rank between 1 and 6)::bigint motor_ex,
                 count(*) filter(where e.motor_place2_rate between 0 and 100 and x.exhibition_time_rank between 1 and 6 and w.wave_height_cm is not null)::bigint motor_ex_wave,
                 count(*) filter(where e.motor_place2_rate between 0 and 100 and x.start_timing_rank between 1 and 6 and w.wind_speed_m is not null)::bigint motor_st_wind
          from v2_race_entries e
          join v2_races r on r.race_id=e.race_id
          join v2_result_entries re on re.race_id=e.race_id and re.lane=e.lane
          left join v2_realtime_exhibition_snapshots x
            on x.race_id=e.race_id and x.lane=e.lane and x.snapshot_label=%s
          left join v2_realtime_weather_snapshots w
            on w.race_id=e.race_id and w.snapshot_label=%s
          where r.race_date between %s and %s and re.finish_position between 1 and 6
        """
        r = one(conn, q, (HIST_LABEL, HIST_LABEL, START_DATE, END_DATE))
        total = int(r.get("rows") or 0)
        print(f"PARTICIPANT_ROWS={total}", flush=True)
        for key in ("motor2","boat2","extime","exrank","exst","exstrank","tilt","wind","wave","motor_ex","motor_ex_wave","motor_st_wind"):
            n = int(r.get(key) or 0)
            pct = 0.0 if total == 0 else 100.0*n/total
            print(f"COVERAGE_{key.upper()}={n}/{total} ({pct:.1f}%)", flush=True)

        motor_bucket = "case when e.motor_place2_rate < 25 then 'M<25' when e.motor_place2_rate < 35 then 'M25-35' when e.motor_place2_rate < 45 then 'M35-45' else 'M45+' end"
        ex_bucket = "case when x.exhibition_time_rank <= 2 then 'EX_TOP2' when x.exhibition_time_rank <= 4 then 'EX_MID' else 'EX_LOW' end"
        st_bucket = "case when x.start_timing_rank <= 2 then 'ST_TOP2' when x.start_timing_rank <= 4 then 'ST_MID' else 'ST_LOW' end"
        wave_bucket = "case when w.wave_height_cm < 3 then 'W<3' when w.wave_height_cm < 6 then 'W3-6' when w.wave_height_cm < 10 then 'W6-10' else 'W10+' end"
        wind_bucket = "case when w.wind_speed_m < 2 then 'V<2' when w.wind_speed_m < 4 then 'V2-4' when w.wind_speed_m < 6 then 'V4-6' else 'V6+' end"

        density(conn, f"r.venue_id,e.lane,{motor_bucket}", "VENUE_LANE_MOTOR", "e.motor_place2_rate between 0 and 100")
        density(conn, f"r.venue_id,e.lane,{ex_bucket}", "VENUE_LANE_EXRANK", "x.exhibition_time_rank between 1 and 6")
        density(conn, f"r.venue_id,e.lane,{motor_bucket},{ex_bucket}", "VENUE_LANE_MOTOR_EX", "e.motor_place2_rate between 0 and 100 and x.exhibition_time_rank between 1 and 6")
        density(conn, f"r.venue_id,e.lane,{motor_bucket},{wave_bucket}", "VENUE_LANE_MOTOR_WAVE", "e.motor_place2_rate between 0 and 100 and w.wave_height_cm is not null")
        density(conn, f"r.venue_id,e.lane,{st_bucket},{wind_bucket}", "VENUE_LANE_ST_WIND", "x.start_timing_rank between 1 and 6 and w.wind_speed_m is not null")

        tr = one(conn, """
          select count(*)::bigint rows, count(distinct tilt)::bigint distinct_values,
                 min(tilt)::float8 min_tilt, max(tilt)::float8 max_tilt
          from v2_realtime_exhibition_snapshots x
          where x.snapshot_label=%s and x.race_date between %s and %s and x.tilt is not null
        """, (HIST_LABEL, START_DATE, END_DATE))
        print(
            f"TILT_DIAGNOSTIC=rows:{int(tr.get('rows') or 0)} distinct:{int(tr.get('distinct_values') or 0)} "
            f"min:{tr.get('min_tilt')} max:{tr.get('max_tilt')}", flush=True
        )

    print("INTERACTION_READINESS_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"INTERACTION_READINESS_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
