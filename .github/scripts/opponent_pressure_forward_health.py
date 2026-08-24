# -*- coding: utf-8 -*-
"""Read-only health report for v2_opponent_pressure_shadow_v2.

Purpose:
- confirm the daily opponent-pressure Shadow v2 collector is still producing rows;
- compare Shadow race coverage with v2_races by day;
- verify model/train_end/array/matched-opponent integrity;
- keep this research feature isolated from Production decisions.

No DB writes / no LINE / no Production changes.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import psycopg
from psycopg.rows import dict_row

DB = os.getenv("DATABASE_URL", "").strip()
END = date.fromisoformat(os.getenv("OPP_PRESSURE_HEALTH_END", date.today().isoformat()))
DAYS = int(os.getenv("OPP_PRESSURE_HEALTH_DAYS", "7"))
START = END - timedelta(days=max(DAYS - 1, 0))


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")

    print("OPP_PRESSURE_HEALTH_MODE=read_only", flush=True)
    print(f"OPP_PRESSURE_HEALTH_PERIOD={START}..{END}", flush=True)
    print("OPP_PRESSURE_HEALTH_POLICY=shadow_only_no_production_no_line", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")

            cur.execute("select to_regclass('public.v2_opponent_pressure_shadow_v2') as rel")
            rel = cur.fetchone()["rel"]
            if not rel:
                print("OPP_PRESSURE_HEALTH_TABLE=MISSING", flush=True)
                raise SystemExit(2)
            print("OPP_PRESSURE_HEALTH_TABLE=OK", flush=True)

            cur.execute(
                """
                with d as (
                  select generate_series(%s::date,%s::date,'1 day'::interval)::date race_date
                ), r as (
                  select race_date,count(*)::bigint races
                  from v2_races where race_date between %s and %s group by race_date
                ), s as (
                  select race_date,
                         count(*)::bigint rows,
                         count(distinct race_id)::bigint shadow_races,
                         count(*) filter(where model_version=2)::bigint model_ok,
                         count(*) filter(where train_end = race_date - 1)::bigint train_ok,
                         count(*) filter(where cardinality(racer_classes)=6 and cardinality(matched_opponents)=6
                           and cardinality(base_win)=6 and cardinality(base_top3)=6
                           and cardinality(score_win)=6 and cardinality(score_top3)=6
                           and cardinality(adj_win)=6 and cardinality(adj_top3)=6)::bigint arrays_ok,
                         count(*) filter(where 4 <= all(matched_opponents))::bigint matched_ok
                  from v2_opponent_pressure_shadow_v2
                  where race_date between %s and %s
                  group by race_date
                )
                select d.race_date,coalesce(r.races,0) races,coalesce(s.rows,0) rows,
                       coalesce(s.shadow_races,0) shadow_races,coalesce(s.model_ok,0) model_ok,
                       coalesce(s.train_ok,0) train_ok,coalesce(s.arrays_ok,0) arrays_ok,
                       coalesce(s.matched_ok,0) matched_ok
                from d left join r using(race_date) left join s using(race_date)
                order by d.race_date
                """,
                (START, END, START, END, START, END),
            )
            rows = list(cur.fetchall())

            total_races = total_shadow = full_days = active_days = 0
            for r in rows:
                races = int(r["races"] or 0)
                shadow = int(r["shadow_races"] or 0)
                active_days += int(races > 0)
                ok = (
                    races > 0
                    and int(r["rows"] or 0) == races
                    and shadow == races
                    and int(r["model_ok"] or 0) == races
                    and int(r["train_ok"] or 0) == races
                    and int(r["arrays_ok"] or 0) == races
                    and int(r["matched_ok"] or 0) == races
                )
                full_days += int(ok)
                total_races += races
                total_shadow += shadow
                print(
                    "OPP_PRESSURE_HEALTH_DAY="
                    f"{r['race_date']} races:{races} shadow:{shadow} model:{int(r['model_ok'] or 0)} "
                    f"train:{int(r['train_ok'] or 0)} arrays:{int(r['arrays_ok'] or 0)} "
                    f"matched:{int(r['matched_ok'] or 0)} full:{1 if ok else 0}",
                    flush=True,
                )

            pct = 0.0 if total_races == 0 else total_shadow * 100.0 / total_races
            print(
                f"OPP_PRESSURE_HEALTH_SUMMARY=active_days:{active_days} full_days:{full_days} "
                f"races:{total_races} shadow_races:{total_shadow} coverage:{pct:.2f}%",
                flush=True,
            )

            cur.execute(
                """select count(*)::bigint rows,
                          min(race_date) first_date,max(race_date) last_date,
                          pg_total_relation_size('v2_opponent_pressure_shadow_v2')::bigint relation_bytes
                   from v2_opponent_pressure_shadow_v2"""
            )
            s = cur.fetchone()
            print(
                f"OPP_PRESSURE_HEALTH_STORAGE=rows:{int(s['rows'] or 0)} first:{s['first_date']} "
                f"last:{s['last_date']} bytes:{int(s['relation_bytes'] or 0)}",
                flush=True,
            )

    print("OPP_PRESSURE_HEALTH_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_PRESSURE_HEALTH_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
