# -*- coding: utf-8 -*-
"""
analyze_candidate_feature_filters_phase6_pg.py

Phase 6:
現行7ルールを過去データで再現し、展示・気象・選手状態による
「単純で説明可能な1条件フィルター」を時系列分割で検証する読み取り専用分析。

目的:
- N01/N02の展示順位フィルターを正式検証
- 赤字のS01～S05から、追加情報で救える安定サブセグメントがあるか探索
- 過学習を避けるため複雑な多条件総当たりはしない
- 最終的に 1日平均0.7～1.0件程度へ近づける候補群を出す

期間:
  全体 2025-07-01 ～ 2026-06-30
  TRAIN 2025-07-01 ～ 2026-02-28
  VALID 2026-03-01 ～ 2026-04-30
  TEST  2026-05-01 ～ 2026-06-30

重要:
- DB更新なし
- LINE通知なし
- 本番変更なし
- 購入処理なし
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-15 feature-filter-phase6-v1"

START_DATE = os.getenv("BT_START_DATE", "2025-07-01")
END_DATE = os.getenv("BT_END_DATE", "2026-06-30")
TRAIN_END = os.getenv("BT6_TRAIN_END", "2026-03-01")   # exclusive
VALID_END = os.getenv("BT6_VALID_END", "2026-05-01")   # exclusive
MIN_TOTAL_N = int(os.getenv("BT6_MIN_TOTAL_N", "30"))
MIN_TEST_N = int(os.getenv("BT6_MIN_TEST_N", "5"))
TOP_N = int(os.getenv("BT6_TOP_N", "50"))

RULES = [
    {"id":"S01","pr":(6,15),"mr":(21,30),"odds":(30.0,50.0),"rnos":set(range(1,10)),"style":"standard","cat":"ALL","mode":"ev"},
    {"id":"S02","pr":(16,30),"mr":(6,10),"odds":(20.0,30.0),"rnos":{7,8,9},"style":"in_strong","cat":"ALL","mode":"prob"},
    {"id":"S03","pr":(11,25),"mr":(6,10),"odds":(30.0,50.0),"rnos":{7,8,9},"style":"standard","cat":"ALL","mode":"ev"},
    {"id":"S04","pr":(1,5),"mr":(11,20),"odds":(20.0,30.0),"rnos":{1,2,3},"style":"ALL","cat":"ALL","mode":"ev"},
    {"id":"S05","pr":(1,5),"mr":(1,5),"odds":(10.0,20.0),"rnos":set(range(1,13)),"style":"ALL","cat":"all_ladies","mode":"prob"},
    {"id":"N01","pr":(11,25),"mr":(2,5),"odds":(3.0,6.0),"rnos":set(range(7,13)),"style":"ALL","cat":"ALL","mode":"ev"},
    {"id":"N02","pr":(11,20),"mr":(2,5),"odds":(3.0,6.0),"rnos":set(range(7,11)),"style":"ALL","cat":"ALL","mode":"ev"},
]

def sf(v, d=0.0):
    try:
        if v is None or v == "": return d
        return float(v)
    except Exception:
        return d

def si(v, d=0):
    try:
        if v is None or v == "": return d
        return int(float(v))
    except Exception:
        return d

def next_day(s):
    return (datetime.strptime(s,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y-%m-%d")

def month_starts(a,b):
    cur=datetime.strptime(a[:7]+"-01","%Y-%m-%d")
    end=datetime.strptime(b[:7]+"-01","%Y-%m-%d")
    while cur<=end:
        yield cur.strftime("%Y-%m-01")
        if cur.month==12: cur=cur.replace(year=cur.year+1,month=1)
        else: cur=cur.replace(month=cur.month+1)

def month_end(s):
    d=datetime.strptime(s,"%Y-%m-%d")
    if d.month==12: d=d.replace(year=d.year+1,month=1)
    else: d=d.replace(month=d.month+1)
    return d.strftime("%Y-%m-%d")

def match(row, rule):
    return (
        rule["pr"][0] <= si(row.get("prob_rank"),999) <= rule["pr"][1]
        and rule["mr"][0] <= si(row.get("market_rank"),999) <= rule["mr"][1]
        and rule["odds"][0] <= sf(row.get("odds"),0) < rule["odds"][1]
    )

def select_one(rows, mode):
    if not rows: return None
    if mode=="ev":
        return max(rows,key=lambda r:(sf(r.get("raw_ev")),sf(r.get("prob"))))
    return max(rows,key=lambda r:(sf(r.get("prob")),sf(r.get("raw_ev"))))

def fetch_month(ms,mx):
    a=max(START_DATE,ms); b=min(next_day(END_DATE),mx)
    if a>=b:return ([],[],[],[],[],[],[])
    ra=a.replace("-",""); rb=b.replace("-","")
    races=fetch_all("select * from v2_races where race_date >= %s and race_date < %s order by race_date,venue_id,race_no",(a,b))
    entries=fetch_all("select * from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane",(ra,rb))
    odds=fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s order by race_id,ticket",(ra,rb))
    results=fetch_all("select race_id,trifecta_ticket,coalesce(trifecta_payout_yen,trifecta_payout) payout from v2_results where race_id >= %s and race_id < %s",(ra,rb))
    exh=fetch_all("select * from v2_realtime_exhibition_snapshots where race_id >= %s and race_id < %s and snapshot_label='historical' order by race_id,lane",(ra,rb))
    weather=fetch_all("select * from v2_realtime_weather_snapshots where race_id >= %s and race_id < %s and snapshot_label='historical'",(ra,rb))
    cond=fetch_all("select * from v2_realtime_racer_condition_snapshots where race_id >= %s and race_id < %s and snapshot_label='historical' order by race_id,lane",(ra,rb))
    return races,entries,odds,results,exh,weather,cond

def metrics(rows):
    n=len(rows); hits=sum(r["hit"] for r in rows); ret=sum(r["ret"] for r in rows); inv=n*100
    return {"n":n,"hits":hits,"hit_rate":hits/n*100 if n else 0,"roi":ret/inv*100 if inv else 0,"profit":ret-inv}

def split(rows):
    tr=[r for r in rows if r["date"] < TRAIN_END]
    va=[r for r in rows if TRAIN_END <= r["date"] < VALID_END]
    te=[r for r in rows if VALID_END <= r["date"] <= END_DATE]
    return tr,va,te

def positive_month_ratio(rows):
    months=defaultdict(list)
    for r in rows: months[r["date"][:7]].append(r)
    if not months:return 0
    pos=sum(1 for seg in months.values() if metrics(seg)["profit"]>0)
    return pos/len(months)*100

def pred_label(name, fn):
    return {"name":name,"fn":fn}

FILTERS = [
    pred_label("BASE", lambda r: True),
    pred_label("EXH_RANK_1", lambda r: r["exh_rank"] == 1),
    pred_label("EXH_RANK_1_2", lambda r: r["exh_rank"] in (1,2)),
    pred_label("EXH_RANK_1_3", lambda r: r["exh_rank"] in (1,2,3)),
    pred_label("EXH_ST_RANK_1_3", lambda r: r["st_rank"] in (1,2,3)),
    pred_label("EXH_ST_RANK_3_4", lambda r: r["st_rank"] in (3,4)),
    pred_label("EXH_ST_RANK_3_6", lambda r: r["st_rank"] in (3,4,5,6)),
    pred_label("WIND_LT4", lambda r: r["wind"] is not None and r["wind"] < 4),
    pred_label("WIND_LT6", lambda r: r["wind"] is not None and r["wind"] < 6),
    pred_label("WAVE_LT6", lambda r: r["wave"] is not None and r["wave"] < 6),
    pred_label("WEATHER_CLEAR", lambda r: r["weather"] == "晴"),
    pred_label("WEATHER_CLEAR_CLOUD", lambda r: r["weather"] in ("晴","曇","くもり")),
    pred_label("PREV_ST_LT010", lambda r: r["prev_st"] is not None and r["prev_st"] < .10),
    pred_label("PREV_ST_LT015", lambda r: r["prev_st"] is not None and r["prev_st"] < .15),
]

def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")

    print(f"✅ analyze_candidate_feature_filters_phase6_pg.py VERSION {VERSION}",flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE} TRAIN_END={TRAIN_END} VALID_END={VALID_END}",flush=True)
    print("読み取り専用。複雑な多条件総当たりは行いません。",flush=True)

    by_rule=defaultdict(list)

    for ms in month_starts(START_DATE,END_DATE):
        races,er,orr,rr,xr,wr,cr=fetch_month(ms,month_end(ms))
        eb=defaultdict(list)
        for x in er: eb[str(x.get("race_id") or "")].append(x)
        ob=defaultdict(dict)
        for x in orr:
            rid=str(x.get("race_id") or ""); t=v24._norm_ticket(x.get("ticket")); o=sf(x.get("odds"))
            if rid and t and o>0: ob[rid][t]=o
        rb={}
        for x in rr:
            rid=str(x.get("race_id") or ""); t=v24._norm_ticket(x.get("trifecta_ticket")); p=si(x.get("payout"))
            if rid and t and p>0: rb[rid]=(t,p)
        xb=defaultdict(dict)
        for x in xr:
            rid=str(x.get("race_id") or ""); lane=si(x.get("lane"))
            if rid and 1<=lane<=6: xb[rid][lane]=x
        wb={str(x.get("race_id") or ""):x for x in wr if x.get("race_id")}
        cb=defaultdict(dict)
        for x in cr:
            rid=str(x.get("race_id") or ""); lane=si(x.get("lane"))
            if rid and 1<=lane<=6: cb[rid][lane]=x

        ready=0
        for race in races:
            rid=str(race.get("race_id") or "")
            entries=eb.get(rid,[]); odds=ob.get(rid,{}); result=rb.get(rid)
            if len(v24._entry_by_lane(entries))!=6 or not result: continue
            ok,_=v24._validate_odds_snapshot(odds)
            if not ok: continue
            if len(xb.get(rid,{}))!=6: continue
            ready+=1

            venue=str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            rno=si(race.get("race_no"))
            style=v24._infer_venue_style(venue)
            cat=v24._infer_event_category(v24._metadata_text(race))
            ranked=v24._rank_candidates(entries,venue,odds)
            rt,payout=result
            date=str(race.get("race_date") or "")[:10]

            for rule in RULES:
                if rno not in rule["rnos"]:continue
                if rule["style"]!="ALL" and style!=rule["style"]:continue
                if rule["cat"]!="ALL" and cat!=rule["cat"]:continue
                sel=select_one([z for z in ranked if match(z,rule)],rule["mode"])
                if not sel:continue
                ticket=str(sel.get("ticket") or "")
                head=si(ticket.split("-")[0],0)
                ex=xb[rid].get(head,{})
                co=cb.get(rid,{}).get(head,{})
                we=wb.get(rid,{})
                hit=(ticket==rt)
                by_rule[rule["id"]].append({
                    "race_id":rid,"date":date,"ticket":ticket,"hit":hit,
                    "ret":payout if hit else 0,
                    "exh_rank":si(ex.get("exhibition_time_rank"),0) or None,
                    "st_rank":si(ex.get("start_timing_rank"),0) or None,
                    "wind":sf(we.get("wind_speed_m"),None) if we.get("wind_speed_m") is not None else None,
                    "wave":sf(we.get("wave_height_cm"),None) if we.get("wave_height_cm") is not None else None,
                    "weather":str(we.get("weather") or ""),
                    "prev_st":sf(co.get("previous_st"),None) if co.get("previous_st") is not None else None,
                })
        print(f"month={ms[:7]} races={len(races)} ready={ready}",flush=True)

    scored=[]
    print("\n=== simple feature filter validation ===",flush=True)
    for rule in RULES:
        base=by_rule[rule["id"]]
        for f in FILTERS:
            rows=[r for r in base if f["fn"](r)]
            if len(rows)<MIN_TOTAL_N:continue
            tr,va,te=split(rows)
            if len(te)<MIN_TEST_N:continue
            mt,mv,me,mo=metrics(tr),metrics(va),metrics(te),metrics(rows)
            plus=positive_month_ratio(rows)
            robust = (
                mt["roi"]>=100
                and mv["roi"]>=100
                and me["roi"]>=100
                and plus>=55
            )
            score=min(mt["roi"],mv["roi"],me["roi"]) + min(len(rows),300)/30 + plus/10
            scored.append((robust,score,rule["id"],f["name"],rows,mt,mv,me,mo,plus))

    scored.sort(key=lambda x:(x[0],x[1]),reverse=True)
    for i,(robust,score,rid,fname,rows,mt,mv,me,mo,plus) in enumerate(scored[:TOP_N],1):
        print(
            f"{i:02d}. {rid}/{fname} "
            f"OVERALL n={mo['n']} ROI={mo['roi']:.1f}% hit={mo['hit_rate']:.1f}% "
            f"TRAIN={mt['roi']:.1f}% VALID={mv['roi']:.1f}% TEST={me['roi']:.1f}% "
            f"plus_months={plus:.1f}% robust={'PASS' if robust else 'WAIT'}",
            flush=True
        )

    print("\n=== deployment-oriented shortlist ===",flush=True)
    shortlist=[x for x in scored if x[0]]
    if not shortlist:
        print("robust PASSなし",flush=True)
    else:
        for i,x in enumerate(shortlist[:20],1):
            _,score,rid,fname,rows,mt,mv,me,mo,plus=x
            days=len({r["date"] for r in rows})
            print(
                f"{i:02d}. {rid}/{fname} n={mo['n']} "
                f"per_day={mo['n']/365:.3f} days={days}/365 "
                f"ROI={mo['roi']:.1f}% TRAIN={mt['roi']:.1f}% "
                f"VALID={mv['roi']:.1f}% TEST={me['roi']:.1f}% "
                f"plus={plus:.1f}%",
                flush=True
            )

    print("\n=== phase6 finished ===",flush=True)

if __name__=="__main__":
    main()