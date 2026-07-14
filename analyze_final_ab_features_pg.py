# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence
from db_pg import fetch_all, fetch_one

JST = timezone(timedelta(hours=9))
END_DATE = os.getenv("ANALYZE_END_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
START_DATE = os.getenv("ANALYZE_START_DATE") or (datetime.strptime(END_DATE, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"

def si(v, d=0):
    try: return int(float(str(v).replace(",", ""))) if v not in (None, "") else d
    except: return d

def sf(v, d=None):
    try: return float(str(v).replace(",", "")) if v not in (None, "") else d
    except: return d

def nt(v):
    nums=[c for c in str(v or "").replace("－","-") if c in "123456"]
    return f"{nums[0]}-{nums[1]}-{nums[2]}" if len(nums)>=3 else ""

def exists(t):
    r=fetch_one("select exists (select 1 from information_schema.tables where table_schema='public' and table_name=%s) ok",(t,))
    return bool(r and r.get("ok"))

def cols(t):
    return [str(r["column_name"]) for r in fetch_all("select column_name from information_schema.columns where table_schema='public' and table_name=%s order by ordinal_position",(t,))]

def first(cs:Sequence[str], names:Iterable[str]):
    s=set(cs)
    return next((n for n in names if n in s), None)

def pct(n,d): return "-" if not d else f"{n/d*100:.1f}%"

def bw(v):
    if v is None:return "missing"
    if v<=2:return "0-2m"
    if v<=4:return "3-4m"
    return "5m+"

def bwh(v):
    if v is None:return "missing"
    if v<=2:return "0-2cm"
    if v<=5:return "3-5cm"
    return "6cm+"

def br(v):
    if v<=0:return "missing"
    if v<=2:return "1-2位"
    if v<=4:return "3-4位"
    return "5-6位"

def bo(v):
    if v is None or v<=0:return "missing"
    if v<3:return "<3"
    if v<5:return "3-5"
    if v<10:return "5-10"
    return "10+"

def load_results():
    if not exists("v2_results"): return {}
    cs=cols("v2_results")
    tc=first(cs,["trifecta_ticket","result_ticket","ticket"])
    pc=first(cs,["trifecta_payout_yen","trifecta_payout","payout_yen"])
    fc=first(cs,["first_lane"])
    sp=["race_id", f"{tc} ticket" if tc else "null::text ticket", f"{pc} payout" if pc else "0::numeric payout", f"{fc} first_lane" if fc else "null::integer first_lane"]
    end_ex=(datetime.strptime(END_DATE,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y%m%d")
    rows=fetch_all(f"select {','.join(sp)} from v2_results where race_id >= %s and race_id < %s",(START_DATE.replace('-',''),end_ex))
    out={}
    for r in rows:
        rid=str(r.get("race_id") or "")
        t=nt(r.get("ticket")); fl=si(r.get("first_lane"),0) or (si(t.split('-')[0],0) if t else 0)
        if rid: out[rid]={"ticket":t,"payout":si(r.get("payout"),0),"first_lane":fl}
    return out

def load_weather():
    if not exists("v2_realtime_weather_snapshots"):return {}
    rows=fetch_all("select race_id,weather,temperature_c,water_temperature_c,wind_speed_m,wind_direction,wave_height_cm from v2_realtime_weather_snapshots where race_date >= %s and race_date <= %s and snapshot_label=%s",(START_DATE,END_DATE,SNAPSHOT_LABEL))
    return {str(r["race_id"]):r for r in rows if r.get("race_id")}

def load_exh():
    if not exists("v2_realtime_exhibition_snapshots"):return {}
    rows=fetch_all("select race_id,lane,exhibition_time,exhibition_time_rank,start_timing,start_timing_rank from v2_realtime_exhibition_snapshots where race_date >= %s and race_date <= %s and snapshot_label=%s",(START_DATE,END_DATE,SNAPSHOT_LABEL))
    out=defaultdict(dict)
    for r in rows:
        rid=str(r.get("race_id") or ""); lane=si(r.get("lane"))
        if rid and 1<=lane<=6: out[rid][lane]=r
    return dict(out)

def load_entry():
    if not exists("v2_realtime_entry_snapshots"):return {}
    rows=fetch_all("select race_id,lane,is_course_changed from v2_realtime_entry_snapshots where race_date >= %s and race_date <= %s and snapshot_label=%s",(START_DATE,END_DATE,SNAPSHOT_LABEL))
    out=defaultdict(dict)
    for r in rows:
        rid=str(r.get("race_id") or ""); lane=si(r.get("lane"))
        if rid and 1<=lane<=6: out[rid][lane]=r
    return dict(out)

def load_fav():
    if not exists("v2_realtime_odds_snapshots"):return {}
    rows=fetch_all("select race_id,ticket,odds,odds_delta_pct,is_odds_drift,is_odds_steam from v2_realtime_odds_snapshots where race_date >= %s and race_date <= %s and snapshot_label=%s and market_rank=1",(START_DATE,END_DATE,SNAPSHOT_LABEL))
    return {str(r["race_id"]):r for r in rows if r.get("race_id")}

def add(a:Dict[str,Counter],k:str,fl:int,hit:bool):
    c=a.setdefault(k,Counter()); c["races"]+=1; c["lane1"]+=int(fl==1); c["favhit"]+=int(hit)

def show(title,a):
    print("\n"+title)
    for k in sorted(a):
        c=a[k]; print(f"  {k}: races={c['races']} 1号艇1着={c['lane1']} ({pct(c['lane1'],c['races'])}) 1番人気的中={c['favhit']} ({pct(c['favhit'],c['races'])})")

def main():
    if not os.getenv("DATABASE_URL"): raise RuntimeError("DATABASE_URL が必要です。")
    print("✅ analyze_final_ab_features_pg.py VERSION 2026-07-14")
    print(f"PERIOD={START_DATE}..{END_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL}")
    print("読み取り専用です。LINE送信・DB更新は行いません。")
    res=load_results(); wea=load_weather(); exh=load_exh(); ent=load_entry(); fav=load_fav()
    print(f"loaded results={len(res)} weather={len(wea)} exhibition_races={len(exh)} entry_races={len(ent)} favorite_odds={len(fav)}")
    ids=sorted(set(res)&set(wea)&set(fav)); print(f"joined_base_races={len(ids)}")
    aggs=[{} for _ in range(8)]
    full=0
    for rid in ids:
        r=res[rid]; w=wea[rid]; f=fav[rid]; e=exh.get(rid,{}); en=ent.get(rid,{})
        fl=si(r.get("first_lane")); rt=nt(r.get("ticket")); ft=nt(f.get("ticket")); hit=bool(rt and ft and rt==ft)
        add(aggs[0],bw(sf(w.get("wind_speed_m"))),fl,hit)
        add(aggs[1],bwh(sf(w.get("wave_height_cm"))),fl,hit)
        add(aggs[2],str(w.get("wind_direction") or "missing"),fl,hit)
        add(aggs[5],bo(sf(f.get("odds"))),fl,hit)
        move="steam(-15%以上)" if f.get("is_odds_steam") else ("drift(+15%以上)" if f.get("is_odds_drift") else "stable")
        add(aggs[7],move,fl,hit)
        add(aggs[6],"進入変更あり" if any(bool(x.get("is_course_changed")) for x in en.values()) else "進入変更なし",fl,hit)
        if e:
            full+=int(len(e)==6)
            add(aggs[3],br(si((e.get(1) or {}).get("exhibition_time_rank"))),fl,hit)
            head=si(ft.split("-")[0]) if ft else 0
            add(aggs[4],br(si((e.get(head) or {}).get("exhibition_time_rank"))),fl,hit)
    print(f"full_6_lane_exhibition={full}")
    titles=["【風速別】","【波高別】","【風向別】","【1号艇 展示タイム順位別】","【1番人気の頭艇 展示タイム順位別】","【1番人気オッズ帯別】","【進入変更有無】","【1番人気オッズ変動別】"]
    for t,a in zip(titles,aggs): show(t,a)
    print("\n注意: 全対象レースの傾向であり、BUY候補限定ROIではありません。")
    print("=== final_ab feature analysis finished ===")
if __name__=="__main__": main()