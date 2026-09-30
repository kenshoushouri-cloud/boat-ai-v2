# -*- coding: utf-8 -*-
"""Read-only historical beforeinfo coverage audit."""
from __future__ import annotations

import argparse
import json
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row


def audit(start_date: str, end_date: str) -> dict[str, Any]:
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute(
                """
                with races as (
                  select race_id,race_date
                    from v2_races
                   where race_date between %s and %s
                ),
                ex as (
                  select e.race_id,
                         count(*) filter(
                           where e.snapshot_label='historical'
                             and e.exhibition_time is not null
                         ) as time_n,
                         count(*) filter(
                           where e.snapshot_label='historical'
                             and e.start_timing is not null
                         ) as st_n
                    from v2_realtime_exhibition_snapshots e
                    join races r using(race_id)
                   group by e.race_id
                ),
                wx as (
                  select w.race_id,
                         max((w.snapshot_label='historical'
                              and w.temperature_c is not null)::int) as temp_ok,
                         max((w.snapshot_label='historical'
                              and w.water_temperature_c is not null)::int) as water_ok,
                         max((w.snapshot_label='historical'
                              and w.wind_speed_m is not null)::int) as wind_ok,
                         max((w.snapshot_label='historical'
                              and w.wave_height_cm is not null)::int) as wave_ok
                    from v2_realtime_weather_snapshots w
                    join races r using(race_id)
                   group by w.race_id
                )
                select to_char(r.race_date,'YYYY-MM') as month_key,
                       count(*) as races,
                       count(*) filter(where coalesce(ex.time_n,0)=6) as exhibition_time6,
                       count(*) filter(where coalesce(ex.st_n,0)=6) as exhibition_st6,
                       count(*) filter(where coalesce(wx.temp_ok,0)=1) as temperature,
                       count(*) filter(where coalesce(wx.water_ok,0)=1) as water_temperature,
                       count(*) filter(where coalesce(wx.wind_ok,0)=1) as wind_speed,
                       count(*) filter(where coalesce(wx.wave_ok,0)=1) as wave_height,
                       count(*) filter(
                         where coalesce(ex.time_n,0)=6
                           and coalesce(ex.st_n,0)=6
                           and coalesce(wx.temp_ok,0)=1
                           and coalesce(wx.water_ok,0)=1
                           and coalesce(wx.wind_ok,0)=1
                           and coalesce(wx.wave_ok,0)=1
                       ) as complete_beforeinfo
                  from races r
                  left join ex using(race_id)
                  left join wx using(race_id)
                 group by 1
                 order by 1
                """,
                (start_date,end_date),
            )
            rows=[dict(x) for x in cur.fetchall()]
        conn.rollback()

    totals={
        "races":0,
        "exhibition_time6":0,
        "exhibition_st6":0,
        "temperature":0,
        "water_temperature":0,
        "wind_speed":0,
        "wave_height":0,
        "complete_beforeinfo":0,
    }
    for row in rows:
        for key in totals:
            totals[key]+=int(row.get(key) or 0)
        races=max(1,int(row.get("races") or 0))
        row["complete_beforeinfo_pct"]=round(
            100.0*int(row.get("complete_beforeinfo") or 0)/races,2
        )
    total_races=max(1,totals["races"])
    totals["complete_beforeinfo_pct"]=round(
        100.0*totals["complete_beforeinfo"]/total_races,2
    )
    return {
        "contract":"HISTORICAL_BEFOREINFO_COVERAGE_AUDIT_V1",
        "start_date":start_date,
        "end_date":end_date,
        "snapshot_label":"historical",
        "read_only":True,
        "db_write":False,
        "result_odds_payout_read":False,
        "months":rows,
        "totals":totals,
        "production_change":False,
        "purchase_action":False,
    }


def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--start-date",required=True)
    ap.add_argument("--end-date",required=True)
    ap.add_argument("--output",default="historical-beforeinfo-coverage.json")
    args=ap.parse_args()
    payload=audit(args.start_date,args.end_date)
    with open(args.output,"w",encoding="utf-8") as f:
        json.dump(payload,f,ensure_ascii=False,indent=2,sort_keys=True)
        f.write("\n")
    for row in payload["months"]:
        print(
            "HIST_BEFOREINFO_COVERAGE_MONTH="
            + " ".join(f"{k}:{v}" for k,v in row.items()),
            flush=True,
        )
    print(
        "HIST_BEFOREINFO_COVERAGE_TOTAL="
        + json.dumps(payload["totals"],sort_keys=True),
        flush=True,
    )
    print("HIST_BEFOREINFO_COVERAGE_RESULT=PASS_READ_ONLY",flush=True)


if __name__=="__main__":
    main()
