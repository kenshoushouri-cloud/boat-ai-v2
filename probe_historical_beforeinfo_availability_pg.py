# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from collections import defaultdict
from typing import Any
from db_pg import fetch_all
import v21_realtime_collector_pg as v21

PROBE_DATE=os.getenv("HIST_PROBE_DATE","2025-07-01").strip()
MAX_VENUES=max(1,int(os.getenv("HIST_PROBE_MAX_VENUES","3")))
RACE_NOS=[int(x) for x in os.getenv("HIST_PROBE_RACE_NOS","1,6,12").split(",") if x.strip().isdigit()]

def has(v:Any)->bool:
    return v is not None and v!=""

def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")
    print("✅ probe_historical_beforeinfo_availability_pg.py VERSION 2026-08-13 historical-beforeinfo-probe-v1",flush=True)
    print(f"HIST_PROBE_DATE={PROBE_DATE} MAX_VENUES={MAX_VENUES} RACE_NOS={RACE_NOS}",flush=True)
    print("読み取り専用。DB更新・LINE通知・本番変更なし。",flush=True)

    races=fetch_all("""
        select race_id,race_date,venue_id,venue_code,venue_name,race_no,race_name
        from v2_races where race_date=%s order by venue_id,race_no
    """,(PROBE_DATE,))
    byv=defaultdict(list)
    for r in races:
        v=str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
        byv[v].append(r)

    selected=[]
    for v in sorted(byv)[:MAX_VENUES]:
        byr={int(r.get("race_no") or 0):r for r in byv[v]}
        for rno in RACE_NOS:
            if rno in byr:selected.append(byr[rno])

    if not selected:
        print("対象レースなし。",flush=True);return

    ids=[str(r["race_id"]) for r in selected]
    ph=",".join(["%s"]*len(ids))
    er=fetch_all(f"select * from v2_race_entries where race_id in ({ph}) order by race_id,lane",tuple(ids))
    eb=defaultdict(list)
    for e in er: eb[str(e.get("race_id") or "")].append(e)

    s={"samples":0,"http_ok":0,"no_data":0,"weather_any":0,"weather_full":0,
       "exhibition_6":0,"racer_condition_6":0,"weight_values":0,
       "previous_st_values":0,"previous_finish_values":0}

    print("=== probe samples ===",flush=True)
    for r in selected:
        s["samples"]+=1
        rid=str(r["race_id"]);v=str(r.get("venue_id") or r.get("venue_code") or "").zfill(2);rno=int(r["race_no"])
        html=v21._fetch(v21._official_url("beforeinfo",PROBE_DATE,v,rno))
        if not html:
            print(f"{rid} {r.get('venue_name') or v} {rno}R status=FETCH_FAILED",flush=True);continue
        s["http_ok"]+=1
        if v21._looks_no_data(html):
            s["no_data"]+=1
            print(f"{rid} {r.get('venue_name') or v} {rno}R status=NO_DATA",flush=True);continue

        w=v21.parse_weather(html)
        ex=v21.parse_exhibition(html)
        rc,players=v21.parse_beforeinfo_extra(html,eb.get(rid,[]))
        wf=[w.get("weather"),w.get("temperature_c"),w.get("water_temperature_c"),
            w.get("wind_speed_m"),w.get("wind_direction"),w.get("wave_height_cm")]
        wc=sum(has(x) for x in wf)
        if wc>0:s["weather_any"]+=1
        if wc>=5:s["weather_full"]+=1
        if len(ex)==6:s["exhibition_6"]+=1
        pr=[x for x in players if x.get("lane") in (1,2,3,4,5,6)]
        if len(pr)==6:s["racer_condition_6"]+=1
        wv=sum(1 for x in pr if has(x.get("weight_kg")))
        sv=sum(1 for x in pr if has(x.get("previous_st")))
        fv=sum(1 for x in pr if has(x.get("previous_finish")))
        s["weight_values"]+=wv;s["previous_st_values"]+=sv;s["previous_finish_values"]+=fv

        print(f"{rid} {r.get('venue_name') or v} {rno}R status=OK weather={wc}/6 exhibition_rows={len(ex)} racer_condition_rows={len(pr)} weight={wv}/6 prev_st={sv}/6 prev_finish={fv}/6",flush=True)
        print(f"  weather={w.get('weather')} temp={w.get('temperature_c')} water={w.get('water_temperature_c')} wind={w.get('wind_speed_m')} dir={w.get('wind_direction')} wave={w.get('wave_height_cm')}",flush=True)
        if ex:
            q=ex[0]
            print(f"  exhibition sample=lane={q.get('lane')} course={q.get('exhibition_course')} time={q.get('exhibition_time')} st={q.get('start_timing')}",flush=True)

    print("=== probe summary ===",flush=True)
    for k,v in s.items():print(f"{k}={v}",flush=True)
    n=s["samples"] or 1
    print(f"weather_any_rate={s['weather_any']/n*100:.1f}%",flush=True)
    print(f"exhibition_complete_rate={s['exhibition_6']/n*100:.1f}%",flush=True)
    print(f"racer_condition_rate={s['racer_condition_6']/n*100:.1f}%",flush=True)
    if s["http_ok"]==0:
        result="NO"
    elif s["weather_any"]>0 or s["exhibition_6"]>0 or s["racer_condition_6"]>0:
        result="YES"
    else:
        result="PARTIAL/UNKNOWN"
    print(f"HISTORICAL_BEFOREINFO_AVAILABLE={result}",flush=True)
    print("=== probe finished ===",flush=True)

if __name__=="__main__":
    main()