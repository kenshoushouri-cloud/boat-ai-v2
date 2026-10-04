# -*- coding: utf-8 -*-
"""Read-only cost planner for OOS historical beforeinfo backfill.

Counts the exact target races selected by the current historical_beforeinfo
backfill SQL and compares them with Exhibition-Time-only missing races.
No HTTP requests, outcomes, odds, payouts, or DB writes.
"""
from __future__ import annotations
import json, os
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

START=date(2026,7,1)
END=date(2026,9,30)
CONTRACT="V51_BEFOREINFO_BACKFILL_COST_PLAN_V1"

SQL=r"""
with ex as (
  select race_id,
         count(*) filter(where snapshot_label='historical') as row_count,
         count(*) filter(where snapshot_label='historical' and exhibition_time is not null) as time_count,
         count(*) filter(where snapshot_label='historical' and start_timing is not null) as st_count
    from v2_realtime_exhibition_snapshots
   group by race_id
),
wx as (
  select race_id,
         max((weather is not null)::int) as weather_ok,
         max((temperature_c is not null)::int) as temp_ok,
         max((water_temperature_c is not null)::int) as water_temp_ok,
         max((wind_speed_m is not null)::int) as wind_ok,
         max((wave_height_cm is not null)::int) as wave_ok
    from v2_realtime_weather_snapshots
   where snapshot_label='historical'
   group by race_id
)
select r.race_id,r.race_date,
       coalesce(ex.row_count,0)::int as ex_rows,
       coalesce(ex.time_count,0)::int as ex_times,
       coalesce(ex.st_count,0)::int as ex_st,
       coalesce(wx.weather_ok,0)::int as wx_weather,
       coalesce(wx.temp_ok,0)::int as wx_temp,
       coalesce(wx.water_temp_ok,0)::int as wx_water_temp,
       coalesce(wx.wind_ok,0)::int as wx_wind,
       coalesce(wx.wave_ok,0)::int as wx_wave
  from v2_races r
  left join ex using(race_id)
  left join wx using(race_id)
 where r.race_date between %s and %s
 order by r.race_date,r.race_id
"""

def main():
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db: raise RuntimeError("DATABASE_URL required")
    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute(SQL,(START,END))
            rows=[dict(x) for x in cur.fetchall()]
        conn.rollback()

    monthly=defaultdict(Counter)
    daily=defaultdict(Counter)
    total=Counter()
    for r in rows:
        ds=str(r["race_date"]); month=ds[:7]
        ex_time_missing=int(r["ex_times"])<6
        current_target=(
            int(r["ex_rows"])<6 or int(r["ex_times"])<6 or int(r["ex_st"])<6
            or int(r["wx_weather"])==0 or int(r["wx_temp"])==0
            or int(r["wx_water_temp"])==0 or int(r["wx_wind"])==0
            or int(r["wx_wave"])==0
        )
        weather_missing=(
            int(r["wx_weather"])==0 or int(r["wx_temp"])==0
            or int(r["wx_water_temp"])==0 or int(r["wx_wind"])==0
            or int(r["wx_wave"])==0
        )
        for c in (total,monthly[month],daily[ds]):
            c["races"]+=1
            c["ex_time_missing"]+=int(ex_time_missing)
            c["current_backfill_http_target"]+=int(current_target)
            c["extra_http_due_other_fields"]+=int(current_target and not ex_time_missing)
            c["st_missing"]+=int(int(r["ex_st"])<6)
            c["weather_missing"]+=int(weather_missing)

    out={
      "contract":CONTRACT,
      "period":[START.isoformat(),END.isoformat()],
      "total":dict(total),
      "monthly":{k:dict(v) for k,v in sorted(monthly.items())},
      "daily":{k:dict(v) for k,v in sorted(daily.items())},
      "http_sleep_seconds_at_0p50":{
        "exhibition_only": total["ex_time_missing"]*0.5,
        "current_backfill_sql": total["current_backfill_http_target"]*0.5,
      },
      "result_read":False,"odds_read":False,"payout_read":False,
      "http_requests_performed":0,"database_write":False,"production_change":False,
    }
    Path("v51-beforeinfo-backfill-cost-plan.json").write_text(
      json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("V51_BF_PLAN_TOTAL="+json.dumps(out["total"],sort_keys=True),flush=True)
    for k,v in out["monthly"].items():
        print("V51_BF_PLAN_MONTH="+json.dumps({"month":k,**v},sort_keys=True),flush=True)
    print("V51_BF_PLAN_SLEEP="+json.dumps(out["http_sleep_seconds_at_0p50"],sort_keys=True),flush=True)
    print("V51_BF_PLAN_HTTP_PERFORMED=0 DB_WRITE=0 RESULT_READ=0",flush=True)
    print("V51_BF_PLAN_RESULT=PASS_READ_ONLY",flush=True)

if __name__=="__main__": main()
