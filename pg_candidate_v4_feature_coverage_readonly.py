# -*- coding: utf-8 -*-
"""Candidate-v4 historical feature coverage audit. SELECT-only."""
from __future__ import annotations
import argparse, json, os
import psycopg
from psycopg.rows import dict_row

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--start-date",default="2025-07-01")
    ap.add_argument("--end-date",required=True)
    args=ap.parse_args()
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db: raise RuntimeError("DATABASE_URL required")
    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
      with conn.cursor() as cur:
        cur.execute("set transaction read only")
        cur.execute("set local statement_timeout='180s'")
        cur.execute("""select table_name,column_name,udt_name from information_schema.columns where table_schema='public'""")
        schema={}
        for r in cur.fetchall(): schema.setdefault(r["table_name"],{})[r["column_name"]]=r["udt_name"]
        def has(t,*cs): return t in schema and all(c in schema[t] for c in cs)
        cur.execute("""select to_char(race_date,'YYYY-MM') month_key,count(*) races
          from v2_races where race_date between %s and %s group by 1 order by 1""",(args.start_date,args.end_date))
        months={r["month_key"]:dict(r) for r in cur.fetchall()}
        def add_complete(key,table,having,cols,extra=""):
          if not has(table,"race_id",*cols): return
          cur.execute(f"""select substr(race_id,1,4)||'-'||substr(race_id,5,2) month_key,count(*) n from
            (select race_id from {table} where race_id between %s and %s {extra}
             group by race_id having {having}) x group by 1 order by 1""",
            (args.start_date.replace("-","")+"_00_00",args.end_date.replace("-","")+"_99_99"))
          for r in cur.fetchall(): months.setdefault(r["month_key"],{})[key]=int(r["n"])
        add_complete("hist_exhibition_time6","v2_realtime_exhibition_snapshots",
          "count(distinct lane) filter(where exhibition_time is not null)=6",
          ("lane","exhibition_time","snapshot_label"),"and snapshot_label='historical'")
        add_complete("hist_exhibition_st6","v2_realtime_exhibition_snapshots",
          "count(distinct lane) filter(where start_timing is not null)=6",
          ("lane","start_timing","snapshot_label"),"and snapshot_label='historical'")
        add_complete("hist_racer6","v2_realtime_racer_condition_snapshots",
          "count(distinct lane)=6",("lane","snapshot_label"),"and snapshot_label='historical'")
        def add_race_flag(key,table,expr,cols,extra=""):
          if not has(table,"race_id",*cols): return
          cur.execute(f"""select substr(race_id,1,4)||'-'||substr(race_id,5,2) month_key,
            count(distinct race_id) filter(where {expr}) n from {table}
            where race_id between %s and %s {extra} group by 1 order by 1""",
            (args.start_date.replace("-","")+"_00_00",args.end_date.replace("-","")+"_99_99"))
          for r in cur.fetchall(): months.setdefault(r["month_key"],{})[key]=int(r["n"])
        for key,col in [("temperature","temperature_c"),("water_temperature","water_temperature_c"),
                        ("wind_speed","wind_speed_m"),("wave_height","wave_height_cm")]:
          add_race_flag(key,"v2_realtime_weather_snapshots",f"{col} is not null",(col,"snapshot_label"),"and snapshot_label='historical'")
        if has("v2_race_entries","recent_form"):
          typ=schema["v2_race_entries"]["recent_form"]
          expr=("jsonb_typeof(recent_form)='array' and jsonb_array_length(recent_form)>0" if typ=="jsonb"
                else "nullif(trim(recent_form::text),'') is not null and trim(recent_form::text) not in ('[]','{}','null')")
          add_complete("recent_form6","v2_race_entries",
            f"count(distinct lane) filter(where {expr})=6",("lane","recent_form"))
        # Historical opponent replay: strict historical model_version=102 contract.
        if has("v2_opponent_pressure_shadow_v2","race_id","lane","model_version"):
          add_complete("opponent6","v2_opponent_pressure_shadow_v2",
            "count(distinct lane)=6",("lane","model_version"),"and model_version=102")
        conn.rollback()
    print("MONTH|RACES|EXH_TIME6|EXH_ST6|TEMP|WATER_TEMP|WIND|WAVE|RACER6|OPPONENT6|RECENT_FORM6")
    keys=["races","hist_exhibition_time6","hist_exhibition_st6","temperature","water_temperature","wind_speed","wave_height","hist_racer6","opponent6","recent_form6"]
    for m in sorted(months):
      print(m+"|"+"|".join(str(int(months[m].get(k,0) or 0)) for k in keys))
    print("CANDIDATE_V4_FEATURE_COVERAGE=PASS_READ_ONLY")
if __name__=="__main__": main()
