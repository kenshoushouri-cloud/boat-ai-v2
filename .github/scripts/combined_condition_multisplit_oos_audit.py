# -*- coding: utf-8 -*-
"""Read-only multi-split OOS stability audit for coarse combined condition features.

Evaluates venue x lane baselines with motor, exhibition, wave and wind buckets.
No coefficients are emitted and no DB/Prediction/Shadow/LINE writes occur.
"""
from __future__ import annotations

import os
from datetime import date

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
START = date(2025, 7, 1)
END = date(2026, 8, 22)
SPLITS = (date(2026, 3, 31), date(2026, 4, 30), date(2026, 5, 31))
HIST = "historical"
TRAIN_BUCKET_MIN = 50
OOS_BUCKET_MIN = 20
TRAIN_BASE_MIN = 300
OOS_BASE_MIN = 80
SHRINK_K = 100.0
WIN_MIN = 0.010
TOP3_MIN = 0.015

MOTOR = "case when e.motor_place2_rate < 25 then 'M<25' when e.motor_place2_rate < 35 then 'M25-35' when e.motor_place2_rate < 45 then 'M35-45' else 'M45+' end"
EX = "case when x.exhibition_time_rank <= 2 then 'EX_TOP2' when x.exhibition_time_rank <= 4 then 'EX_MID' else 'EX_LOW' end"
ST = "case when x.start_timing_rank <= 2 then 'ST_TOP2' when x.start_timing_rank <= 4 then 'ST_MID' else 'ST_LOW' end"
WAVE = "case when w.wave_height_cm < 3 then 'W<3' when w.wave_height_cm < 6 then 'W3-6' when w.wave_height_cm < 10 then 'W6-10' else 'W10+' end"
WIND = "case when w.wind_speed_m < 2 then 'V<2' when w.wind_speed_m < 4 then 'V2-4' when w.wind_speed_m < 6 then 'V4-6' else 'V6+' end"

FEATURES = {
    "MOTOR": (MOTOR, "e.motor_place2_rate between 0 and 100"),
    "EX": (EX, "x.exhibition_time_rank between 1 and 6"),
    "MOTOR_EX": (f"({MOTOR}) || '|' || ({EX})", "e.motor_place2_rate between 0 and 100 and x.exhibition_time_rank between 1 and 6"),
    "WAVE": (WAVE, "w.wave_height_cm is not null"),
    "MOTOR_WAVE": (f"({MOTOR}) || '|' || ({WAVE})", "e.motor_place2_rate between 0 and 100 and w.wave_height_cm is not null"),
    "ST": (ST, "x.start_timing_rank between 1 and 6"),
    "WIND": (WIND, "w.wind_speed_m is not null"),
    "ST_WIND": (f"({ST}) || '|' || ({WIND})", "x.start_timing_rank between 1 and 6 and w.wind_speed_m is not null"),
}


def one(conn, q, p=()):
    with conn.cursor() as cur:
        cur.execute(q, p)
        return dict(cur.fetchone() or {})


def pct(a: int, b: int) -> float:
    return 0.0 if not b else 100.0 * a / b


def audit(conn, split: date, feature: str, bucket: str, usable: str) -> dict:
    q = f"""
    with base as (
      select r.race_date, r.venue_id, e.lane, {bucket} as bucket,
             case when re.finish_position=1 then 1.0 else 0.0 end win,
             case when re.finish_position between 1 and 3 then 1.0 else 0.0 end top3
      from v2_race_entries e
      join v2_races r on r.race_id=e.race_id
      join v2_result_entries re on re.race_id=e.race_id and re.lane=e.lane
      left join v2_realtime_exhibition_snapshots x
        on x.race_id=e.race_id and x.lane=e.lane and x.snapshot_label=%s
      left join v2_realtime_weather_snapshots w
        on w.race_id=e.race_id and w.snapshot_label=%s
      where r.race_date between %s and %s
        and re.finish_position between 1 and 6 and {usable}
    ),
    tb as (
      select venue_id,lane,bucket,count(*)::bigint n,avg(win)::float8 wr,avg(top3)::float8 tr
      from base where race_date<=%s group by venue_id,lane,bucket
    ),
    tbase as (
      select venue_id,lane,count(*)::bigint n,avg(win)::float8 wr,avg(top3)::float8 tr
      from base where race_date<=%s group by venue_id,lane
    ),
    ob as (
      select venue_id,lane,bucket,count(*)::bigint n,avg(win)::float8 wr,avg(top3)::float8 tr
      from base where race_date>%s group by venue_id,lane,bucket
    ),
    obase as (
      select venue_id,lane,count(*)::bigint n,avg(win)::float8 wr,avg(top3)::float8 tr
      from base where race_date>%s group by venue_id,lane
    ),
    m as (
      select tb.n tn,ob.n onum,
             (tb.wr-tbase.wr) tw,(ob.wr-obase.wr) ow,
             (tb.tr-tbase.tr) tt,(ob.tr-obase.tr) ot,
             tb.n::float8/(tb.n+%s) shrink
      from tb join ob using(venue_id,lane,bucket)
      join tbase using(venue_id,lane) join obase using(venue_id,lane)
      where tb.n>=%s and ob.n>=%s and tbase.n>=%s and obase.n>=%s
    )
    select count(*)::bigint matched,
      count(*) filter(where abs(tw*shrink)>=%s)::bigint win_meaningful,
      count(*) filter(where abs(tw*shrink)>=%s and tw*ow>0)::bigint win_agree,
      count(*) filter(where abs(tt*shrink)>=%s)::bigint top3_meaningful,
      count(*) filter(where abs(tt*shrink)>=%s and tt*ot>0)::bigint top3_agree,
      coalesce(avg(abs(tw*shrink)),0)::float8 win_abs,
      coalesce(avg(abs(tt*shrink)),0)::float8 top3_abs
    from m
    """
    return one(conn, q, (
        HIST,HIST,START,END,split,split,split,split,SHRINK_K,
        TRAIN_BUCKET_MIN,OOS_BUCKET_MIN,TRAIN_BASE_MIN,OOS_BASE_MIN,
        WIN_MIN,WIN_MIN,TOP3_MIN,TOP3_MIN,
    ))


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    print("COMBINED_OOS_MODE=read_only", flush=True)
    print(f"COMBINED_OOS_PERIOD={START}..{END}", flush=True)
    print("COMBINED_OOS_POLICY=no_coefficients_no_writes_no_prediction_no_shadow_no_line", flush=True)
    print(f"COMBINED_OOS_GATES=train_bucket>={TRAIN_BUCKET_MIN},oos_bucket>={OOS_BUCKET_MIN},train_base>={TRAIN_BASE_MIN},oos_base>={OOS_BASE_MIN},shrink_k={SHRINK_K}", flush=True)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
        print("COMBINED_OOS_SESSION=parallel_off,work_mem_8MB,timeout_120s", flush=True)
        for split in SPLITS:
            print(f"SPLIT={split}", flush=True)
            for name,(bucket,usable) in FEATURES.items():
                r=audit(conn,split,name,bucket,usable)
                m=int(r.get('matched') or 0); wm=int(r.get('win_meaningful') or 0); wa=int(r.get('win_agree') or 0)
                tm=int(r.get('top3_meaningful') or 0); ta=int(r.get('top3_agree') or 0)
                print(f"COMBO_{name}=matched:{m} win:{wa}/{wm}({pct(wa,wm):.1f}%) top3:{ta}/{tm}({pct(ta,tm):.1f}%) mean_abs_win_pt:{100*float(r.get('win_abs') or 0):.2f} mean_abs_top3_pt:{100*float(r.get('top3_abs') or 0):.2f}", flush=True)
    print("COMBINED_OOS_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f"COMBINED_OOS_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}", flush=True)
        raise
