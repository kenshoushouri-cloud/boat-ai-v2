# -*- coding: utf-8 -*-
"""
analyze_n02_phase9_frequency_extension_pg.py

購入頻度を安全に増やせるかを固定条件で検証する読み取り専用Phase9。

CORE:
  N02_WIND_LT4
  pr 11-20 / mr 2-5 / odds 3-6 / R07-10 / EV MAX / wind<4

EXTENSION:
  N01_WIND_LT4 のうち、そのレースでCORE候補が存在しないレースだけ追加。
  N01 = pr 11-25 / mr 2-5 / odds 3-6 / R07-12 / EV MAX
  wind<4

つまりCOREの条件を緩めて置換するのではなく、
「COREに買い目がないレース」だけN01範囲から第2買い目候補として追加する。

閾値探索なし。既に過去Phase6で固定済みのN01/N02定義だけを使用。
比較:
  CORE_ONLY
  EXTENSION_ONLY
  CORE_PLUS_EXTENSION

100円/1候補で、ROI・月利益・30日購入数・購入間隔・最大DDを確認する。
"""

from __future__ import annotations
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION="2026-08-17 phase9-frequency-extension-v1"
START=os.getenv("P9_START_DATE","2025-07-01")
END=os.getenv("P9_END_DATE","2026-08-15")
TRAIN_END="2026-03-01"; VALID_END="2026-05-01"; OOS1_START="2026-07-01"; OOS2_START="2026-08-01"
LABELS=["historical","final_ab","final","manual","beforeinfo","pre","day","night","morning"]

def sf(v,d=None):
    try:return float(v) if v not in (None,"") else d
    except:return d
def si(v,d=0):
    try:return int(float(v)) if v not in (None,"") else d
    except:return d
def nxt(s):return (datetime.strptime(s,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y-%m-%d")
def months(a,b):
    d=datetime.strptime(a[:7]+"-01","%Y-%m-%d"); e=datetime.strptime(b[:7]+"-01","%Y-%m-%d")
    while d<=e:
        yield d.strftime("%Y-%m-01")
        d=d.replace(year=d.year+1,month=1) if d.month==12 else d.replace(month=d.month+1)
def mend(s):
    d=datetime.strptime(s,"%Y-%m-%d")
    d=d.replace(year=d.year+1,month=1) if d.month==12 else d.replace(month=d.month+1)
    return d.strftime("%Y-%m-%d")
def period(ds):
    if ds<TRAIN_END:return "TRAIN"
    if ds<VALID_END:return "VALID"
    if ds<OOS1_START:return "TEST"
    if ds<OOS2_START:return "OOS1"
    return "OOS2"
def day_count(a,b):return (datetime.strptime(b,"%Y-%m-%d").date()-datetime.strptime(a,"%Y-%m-%d").date()).days+1
def lp(x):
    try:return LABELS.index(str(x or "").lower())
    except:return 999
def choose_label(xb,wb,cb):
    ls=[l for l,lanes in xb.items() if len(lanes)==6 and l in wb and len(cb.get(l,{}))==6]
    return sorted(ls,key=lambda x:(lp(x),x))[0] if ls else None

def metrics(rows,days=None):
    n=len(rows); hits=sum(int(x["hit"]) for x in rows); ret=sum(x["ret"] for x in rows); inv=n*100
    cur=ls=bank=peak=dd=0
    for x in sorted(rows,key=lambda z:(z["date"],z["race_id"])):
        if x["hit"]:cur=0
        else:cur+=1;ls=max(ls,cur)
        bank+=x["ret"]-100; peak=max(peak,bank); dd=max(dd,peak-bank)
    out={"n":n,"hits":hits,"roi":ret/inv*100 if inv else 0,"profit":ret-inv,"ls":ls,"dd":dd,"active":len({x["date"] for x in rows})}
    if days:
        out["bets30"]=n/days*30.44
        out["profit30"]=(ret-inv)/days*30.44
        out["daysbet"]=days/n if n else 0
    return out
def fm(m):
    return f"n={m['n']} hits={m['hits']} ROI={m['roi']:.1f}% P={m['profit']} LS={m['ls']} DD={m['dd']}"

def match(row,pr_hi,rnos):
    pr=si(row.get("prob_rank"),999); mr=si(row.get("market_rank"),999); o=sf(row.get("odds"),0) or 0
    return 11<=pr<=pr_hi and 2<=mr<=5 and 3.0<=o<6.0 and rnos
def select(rows):
    if not rows:return None
    return max(rows,key=lambda r:(sf(r.get("raw_ev"),0) or 0,sf(r.get("prob"),0) or 0))

def main():
    if not os.getenv("DATABASE_URL"):raise RuntimeError("DATABASE_URL が必要です")
    print(f"✅ analyze_n02_phase9_frequency_extension_pg.py VERSION {VERSION}",flush=True)
    print("固定比較のみ。COREは変更せず、COREなしレースだけEXTENSIONを追加。",flush=True)

    core=[]; ext=[]
    for ms in months(START,END):
        a=max(START,ms); b=min(nxt(END),mend(ms)); ra=a.replace("-",""); rb=b.replace("-","")
        races=fetch_all("select * from v2_races where race_date >= %s and race_date < %s order by race_date,venue_id,race_no",(a,b))
        er=fetch_all("select * from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane",(ra,rb))
        oo=fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s",(ra,rb))
        rr=fetch_all("select race_id,trifecta_ticket,coalesce(trifecta_payout_yen,trifecta_payout) payout from v2_results where race_id >= %s and race_id < %s",(ra,rb))
        ex=fetch_all("select race_id,snapshot_label,lane,exhibition_time from v2_realtime_exhibition_snapshots where race_id >= %s and race_id < %s",(ra,rb))
        ww=fetch_all("select race_id,snapshot_label,wind_speed_m from v2_realtime_weather_snapshots where race_id >= %s and race_id < %s",(ra,rb))
        cc=fetch_all("select race_id,snapshot_label,lane from v2_realtime_racer_condition_snapshots where race_id >= %s and race_id < %s",(ra,rb))
        eb=defaultdict(list)
        for x in er:eb[str(x.get("race_id") or "")].append(x)
        ob=defaultdict(dict)
        for x in oo:
            t=v24._norm_ticket(x.get("ticket")); o=sf(x.get("odds"),0); rid=str(x.get("race_id") or "")
            if rid and t and o and o>0:ob[rid][t]=o
        rb={}
        for x in rr:
            rid=str(x.get("race_id") or ""); t=v24._norm_ticket(x.get("trifecta_ticket")); p=si(x.get("payout"),0)
            if rid and t and p>0:rb[rid]=(t,p)
        xb=defaultdict(lambda:defaultdict(set))
        for x in ex:
            rid=str(x.get("race_id") or ""); l=str(x.get("snapshot_label") or ""); lane=si(x.get("lane"),0)
            if rid and l and 1<=lane<=6 and x.get("exhibition_time") is not None:xb[rid][l].add(lane)
        wb=defaultdict(dict)
        for x in ww:
            rid=str(x.get("race_id") or ""); l=str(x.get("snapshot_label") or "")
            if rid and l:wb[rid][l]=x
        cb=defaultdict(lambda:defaultdict(dict))
        for x in cc:
            rid=str(x.get("race_id") or ""); l=str(x.get("snapshot_label") or ""); lane=si(x.get("lane"),0)
            if rid and l and 1<=lane<=6:cb[rid][l][lane]=x

        mn_core=mn_ext=0
        for race in races:
            rid=str(race.get("race_id") or ""); ent=eb.get(rid,[]); odds=ob.get(rid,{}); res=rb.get(rid)
            if len(v24._entry_by_lane(ent))!=6 or not res:continue
            ok,_=v24._validate_odds_snapshot(odds)
            if not ok:continue
            lab=choose_label(xb.get(rid,{}),wb.get(rid,{}),cb.get(rid,{}))
            if not lab:continue
            wind=sf(wb[rid][lab].get("wind_speed_m"),None)
            if wind is None or wind>=4:continue

            rno=si(race.get("race_no"),0); venue=str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            ranked=v24._rank_candidates(ent,venue,odds)

            core_sel=None
            if 7<=rno<=10:
                core_sel=select([z for z in ranked if match(z,20,True)])

            if core_sel:
                ticket=str(core_sel.get("ticket") or ""); rt,pay=res
                core.append({"race_id":rid,"date":str(race.get("race_date"))[:10],"ticket":ticket,"hit":ticket==rt,"ret":pay if ticket==rt else 0})
                mn_core+=1
                continue

            # CORE候補がないレースだけ N01 extension
            if 7<=rno<=12:
                ext_sel=select([z for z in ranked if match(z,25,True)])
                if ext_sel:
                    ticket=str(ext_sel.get("ticket") or ""); rt,pay=res
                    ext.append({"race_id":rid,"date":str(race.get("race_date"))[:10],"ticket":ticket,"hit":ticket==rt,"ret":pay if ticket==rt else 0})
                    mn_ext+=1

        print(f"month={ms[:7]} core={mn_core} extension={mn_ext}",flush=True)

    total_days=day_count(START,END); union=core+ext
    print("\n=== OVERALL @100yen ===",flush=True)
    for name,rows in [("CORE_ONLY",core),("EXTENSION_ONLY",ext),("CORE_PLUS_EXTENSION",union)]:
        m=metrics(rows,total_days)
        print(f"{name}: {fm(m)} bets/30d={m['bets30']:.2f} days/bet={m['daysbet']:.2f} profit/30d={m['profit30']:.0f}",flush=True)

    print("\n=== PERIOD ===",flush=True)
    for p in ("TRAIN","VALID","TEST","OOS1","OOS2"):
        print(f"--- {p} ---",flush=True)
        for name,rows in [("CORE",core),("EXT",ext),("UNION",union)]:
            seg=[x for x in rows if period(x["date"])==p]
            print(f"{name}: {fm(metrics(seg))}",flush=True)

    print("\n=== MONTHLY ===",flush=True)
    mos=sorted({x["date"][:7] for x in union})
    for mo in mos:
        c=metrics([x for x in core if x["date"].startswith(mo)])
        e=metrics([x for x in ext if x["date"].startswith(mo)])
        u=metrics([x for x in union if x["date"].startswith(mo)])
        print(f"{mo} CORE n={c['n']} ROI={c['roi']:.0f}% P={c['profit']} | EXT n={e['n']} ROI={e['roi']:.0f}% P={e['profit']} | UNION n={u['n']} ROI={u['roi']:.0f}% P={u['profit']}",flush=True)

    print("\nIMPORTANT: EXTENSIONがTEST/OOSで弱ければ頻度目的でも採用しません。",flush=True)
    print("=== phase9 finished ===",flush=True)

if __name__=="__main__":main()