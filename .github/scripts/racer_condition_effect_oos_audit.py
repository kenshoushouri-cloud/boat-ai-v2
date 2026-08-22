# -*- coding: utf-8 -*-
"""Read-only OOS stability audit for racer/venue/lane weather effects.

Tests whether wind/wave effects seen in an earlier period reproduce later.
Each condition bucket is compared with the same group's own baseline.
Only aggregate stability is reported; no racer coefficients are emitted.
No DB writes, prediction changes, Shadow changes, or LINE operations.
"""
from __future__ import annotations

import os
from datetime import date

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
START_DATE = date.fromisoformat(os.getenv("CONDITION_EFFECT_START_DATE", "2025-07-01"))
SPLIT_DATE = date.fromisoformat(os.getenv("CONDITION_EFFECT_SPLIT_DATE", "2026-05-31"))
END_DATE = date.fromisoformat(os.getenv("CONDITION_EFFECT_END_DATE", "2026-08-22"))
HIST_LABEL = "historical"
TRAIN_BUCKET_MIN = 20
OOS_BUCKET_MIN = 10
TRAIN_BASE_MIN = 50
OOS_BASE_MIN = 20
SHRINK_K = 50.0
WIN_MEANINGFUL = 0.01
TOP3_MEANINGFUL = 0.015

DIMENSIONS = {
    "RACER_LANE": ["racer_number", "lane"],
    "RACER_VENUE": ["racer_number", "venue_id"],
    "VENUE_LANE": ["venue_id", "lane"],
}
CONDITIONS = {
    "WIND": (
        "w.wind_speed_m",
        "case when w.wind_speed_m < 2 then '<2' when w.wind_speed_m < 4 then '2-<4' "
        "when w.wind_speed_m < 6 then '4-<6' else '6+' end",
    ),
    "WAVE": (
        "w.wave_height_cm",
        "case when w.wave_height_cm < 3 then '<3' when w.wave_height_cm < 6 then '3-<6' "
        "when w.wave_height_cm < 10 then '6-<10' else '10+' end",
    ),
}


def fetch_one(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row or {})


def columns(conn, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """select column_name from information_schema.columns
               where table_schema='public' and table_name=%s""",
            (table,),
        )
        return {str(r["column_name"]) for r in cur.fetchall()}


def table_exists(conn, table: str) -> bool:
    return bool(
        fetch_one(
            conn,
            """select exists(select 1 from information_schema.tables
               where table_schema='public' and table_name=%s) ok""",
            (table,),
        ).get("ok")
    )


def group_expr(name: str) -> sql.SQL:
    if name == "racer_number":
        return sql.SQL("e.racer_number")
    if name == "lane":
        return sql.SQL("e.lane")
    if name == "venue_id":
        return sql.SQL("r.venue_id")
    raise ValueError(name)


def eq_join(left: str, right: str, count: int) -> sql.Composed:
    return sql.SQL(" and ").join(
        sql.SQL("{l}.g{n}={r}.g{n}").format(
            l=sql.SQL(left), r=sql.SQL(right), n=sql.SQL(str(i + 1))
        )
        for i in range(count)
    )


def audit_one(conn, dimension: str, condition: str) -> dict:
    group_names = DIMENSIONS[dimension]
    n_groups = len(group_names)
    group_select = sql.SQL(", ").join(
        sql.SQL("{} as g{}").format(group_expr(name), sql.SQL(str(i + 1)))
        for i, name in enumerate(group_names)
    )
    group_cols = sql.SQL(", ").join(
        sql.Identifier(f"g{i + 1}") for i in range(n_groups)
    )
    t_o_join = eq_join("t", "o", n_groups)
    t_tb_join = eq_join("t", "tb", n_groups)
    o_ob_join = eq_join("o", "ob", n_groups)
    nonnull_expr, bucket_expr = CONDITIONS[condition]

    query = sql.SQL("""
      with base as (
        select r.race_date, {group_select}, {bucket_expr} as bucket,
               case when re.finish_position=1 then 1.0 else 0.0 end as win,
               case when re.finish_position between 1 and 3 then 1.0 else 0.0 end as top3
        from v2_race_entries e
        join v2_races r on r.race_id=e.race_id
        join v2_result_entries re
          on re.race_id=e.race_id and re.lane=e.lane
         and re.racer_number=e.racer_number
        join v2_realtime_weather_snapshots w
          on w.race_id=e.race_id and w.snapshot_label=%s
        where r.race_date >= %s and r.race_date <= %s
          and re.finish_position between 1 and 6
          and e.racer_number is not null
          and {nonnull_expr} is not null
      ),
      train_bucket as (
        select {group_cols}, bucket, count(*)::bigint n,
               avg(win)::float8 win_rate, avg(top3)::float8 top3_rate
        from base where race_date <= %s group by {group_cols}, bucket
      ),
      train_base as (
        select {group_cols}, count(*)::bigint n,
               avg(win)::float8 win_rate, avg(top3)::float8 top3_rate
        from base where race_date <= %s group by {group_cols}
      ),
      oos_bucket as (
        select {group_cols}, bucket, count(*)::bigint n,
               avg(win)::float8 win_rate, avg(top3)::float8 top3_rate
        from base where race_date > %s group by {group_cols}, bucket
      ),
      oos_base as (
        select {group_cols}, count(*)::bigint n,
               avg(win)::float8 win_rate, avg(top3)::float8 top3_rate
        from base where race_date > %s group by {group_cols}
      ),
      matched as (
        select t.n train_n, o.n oos_n, tb.n train_base_n, ob.n oos_base_n,
               (t.win_rate-tb.win_rate) train_win_lift,
               (o.win_rate-ob.win_rate) oos_win_lift,
               (t.top3_rate-tb.top3_rate) train_top3_lift,
               (o.top3_rate-ob.top3_rate) oos_top3_lift,
               (t.n::float8/(t.n+%s)) shrink_w
        from train_bucket t
        join oos_bucket o on t.bucket=o.bucket and {t_o_join}
        join train_base tb on {t_tb_join}
        join oos_base ob on {o_ob_join}
        where t.n >= %s and o.n >= %s and tb.n >= %s and ob.n >= %s
      )
      select count(*)::bigint matched,
             count(*) filter(where abs(train_win_lift*shrink_w) >= %s)::bigint win_meaningful,
             count(*) filter(where abs(train_win_lift*shrink_w) >= %s
                              and train_win_lift*oos_win_lift > 0)::bigint win_sign_agree,
             count(*) filter(where abs(train_top3_lift*shrink_w) >= %s)::bigint top3_meaningful,
             count(*) filter(where abs(train_top3_lift*shrink_w) >= %s
                              and train_top3_lift*oos_top3_lift > 0)::bigint top3_sign_agree,
             coalesce(avg(abs(train_win_lift*shrink_w)),0)::float8 mean_abs_shrunk_win_lift,
             coalesce(avg(abs(train_top3_lift*shrink_w)),0)::float8 mean_abs_shrunk_top3_lift
      from matched
    """).format(
        group_select=group_select,
        bucket_expr=sql.SQL(bucket_expr),
        nonnull_expr=sql.SQL(nonnull_expr),
        group_cols=group_cols,
        t_o_join=t_o_join,
        t_tb_join=t_tb_join,
        o_ob_join=o_ob_join,
    )
    return fetch_one(
        conn,
        query,
        (
            HIST_LABEL, START_DATE, END_DATE,
            SPLIT_DATE, SPLIT_DATE, SPLIT_DATE, SPLIT_DATE,
            SHRINK_K,
            TRAIN_BUCKET_MIN, OOS_BUCKET_MIN, TRAIN_BASE_MIN, OOS_BASE_MIN,
            WIN_MEANINGFUL, WIN_MEANINGFUL, TOP3_MEANINGFUL, TOP3_MEANINGFUL,
        ),
    )


def pct(n: int, d: int) -> float:
    return 0.0 if d <= 0 else 100.0 * n / d


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    if not (START_DATE <= SPLIT_DATE < END_DATE):
        raise RuntimeError("invalid train/OOS period")

    print("CONDITION_EFFECT_MODE=read_only", flush=True)
    print(f"CONDITION_EFFECT_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(f"CONDITION_EFFECT_TRAIN={START_DATE}..{SPLIT_DATE}", flush=True)
    print(f"CONDITION_EFFECT_OOS={SPLIT_DATE}..{END_DATE}", flush=True)
    print("CONDITION_EFFECT_SCOPE=wind_wave_only", flush=True)
    print("CONDITION_EFFECT_POLICY=aggregate_stability_no_coefficients_no_writes_no_line", flush=True)
    print(
        f"CONDITION_EFFECT_GATES=train_bucket>={TRAIN_BUCKET_MIN},oos_bucket>={OOS_BUCKET_MIN},"
        f"train_base>={TRAIN_BASE_MIN},oos_base>={OOS_BASE_MIN},shrink_k={SHRINK_K}",
        flush=True,
    )

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        required = [
            "v2_races", "v2_race_entries", "v2_result_entries",
            "v2_realtime_weather_snapshots",
        ]
        missing = [t for t in required if not table_exists(conn, t)]
        if missing:
            print(f"CONDITION_EFFECT_MISSING_TABLES={','.join(missing)}", flush=True)
            raise SystemExit(2)

        ec = columns(conn, "v2_race_entries")
        rc = columns(conn, "v2_races")
        rec = columns(conn, "v2_result_entries")
        wc = columns(conn, "v2_realtime_weather_snapshots")
        bad = {
            "v2_race_entries": {"race_id", "lane", "racer_number"} - ec,
            "v2_races": {"race_id", "race_date", "venue_id"} - rc,
            "v2_result_entries": {"race_id", "lane", "racer_number", "finish_position"} - rec,
            "v2_realtime_weather_snapshots": {"race_id", "snapshot_label", "wind_speed_m", "wave_height_cm"} - wc,
        }
        bad = {k: v for k, v in bad.items() if v}
        if bad:
            print("CONDITION_EFFECT_SCHEMA=FAIL", flush=True)
            raise SystemExit(3)
        print("CONDITION_EFFECT_SCHEMA=PASS", flush=True)

        for condition in ("WIND", "WAVE"):
            for dimension in ("RACER_LANE", "RACER_VENUE", "VENUE_LANE"):
                r = audit_one(conn, dimension, condition)
                matched = int(r.get("matched") or 0)
                wm = int(r.get("win_meaningful") or 0)
                wa = int(r.get("win_sign_agree") or 0)
                tm = int(r.get("top3_meaningful") or 0)
                ta = int(r.get("top3_sign_agree") or 0)
                print(
                    f"EFFECT_{condition}_{dimension}=matched:{matched} "
                    f"win_meaningful:{wm} win_sign_agree:{wa} ({pct(wa,wm):.1f}%) "
                    f"top3_meaningful:{tm} top3_sign_agree:{ta} ({pct(ta,tm):.1f}%) "
                    f"mean_abs_shrunk_win_pt:{100*float(r.get('mean_abs_shrunk_win_lift') or 0):.2f} "
                    f"mean_abs_shrunk_top3_pt:{100*float(r.get('mean_abs_shrunk_top3_lift') or 0):.2f}",
                    flush=True,
                )

    print("CONDITION_EFFECT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
