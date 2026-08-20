# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all
import backtest_v24_motor2_historical_pg as bt

VERSION="2026-08-20 v24-motor2-transition-diagnostic-v1"
START_DATE=os.getenv("MOTOR2_TRANS_START_DATE","2025-07-01").strip()
END_DATE=os.getenv("MOTOR2_TRANS_END_DATE","2026-08-19").strip()
UNIT_YEN=max(1,int(os.getenv("MOTOR2_TRANS_UNIT_YEN","100")))
PROGRESS_EVERY=max(1,int(os.getenv("MOTOR2_TRANS_PROGRESS_EVERY","5000")))
MAX_RACES=max(0,int(os.getenv("MOTOR2_TRANS_MAX_RACES","0")))

CONFIGS=[]
for tok in os.getenv("MOTOR2_TRANS_CONFIGS","A:0.45:0.00,B:0.50:0.10,C:0.60:0.10").split(","):
    n,l,m=tok.strip().split(":")
    CONFIGS.append((n,float(l),float(m)))

def st(): return {"bets":0,"hits":0,"investment":0,"return":0}
def add(s,hit,payout):
    s["bets"]+=1;s["investment"]+=UNIT_YEN
    if hit:s["hits"]+=1;s["return"]+=payout
def roi(s): return s["return"]/s["investment"]*100 if s["investment"] else 0.0
def hr(s): return s["hits"]/s["bets"]*100 if s["bets"] else 0.0

def motor_rank_map(entries):
    xs=[]
    for e in entries:
        lane=bt.si(e.get("lane"),0); m=bt.valid_motor2(e.get("motor_place2_rate"))
        if 1<=lane<=6 and m is not None: xs.append((lane,m))
    xs.sort(key=lambda x:(-x[1],x[0]))
    return {lane:i for i,(lane,_) in enumerate(xs,1)}

def bucket(ticket,mr):
    rs=[mr.get(int(x)) for x in ticket.split("-")]
    if any(x is None for x in rs): return "UNKNOWN"
    b=min(rs)
    return "HAS_M1" if b==1 else "HAS_M2" if b<=2 else "HAS_M3" if b<=3 else "NO_TOP3"

def fetch_month(ms,mx):
    a=max(START_DATE,ms); b=min(bt.next_day(END_DATE),mx)
    if a>=b:return [],[],[],[]
    ra=a.replace("-","");rb=b.replace("-","")
    races=fetch_all("select race_id,race_date,venue_id,venue_code,race_no from v2_races where race_date >= %s and race_date < %s order by race_date,venue_id,race_no",(a,b))
    entries=fetch_all("select race_id,lane,racer_class,national_win_rate,national_place2_rate,local_place2_rate,avg_st,motor_place2_rate from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane",(ra,rb))
    results=fetch_all("select race_id,trifecta_ticket,trifecta_payout_yen from v2_results where race_date >= %s and race_date < %s and result_status='official' and race_status='official' and trifecta_ticket is not null and trifecta_payout_yen > 0",(a,b))
    odds=fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s and odds > 0 order by race_id,ticket",(ra,rb))
    return races,entries,results,odds

def main():
    if not os.getenv("DATABASE_URL"): raise RuntimeError("DATABASE_URL ãå¿è¦ã§ãã")
    print(f"â diagnose_v24_motor2_transitions_pg.py VERSION {VERSION}",flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE} CONFIGS={CONFIGS}",flush=True)
    print("READ_ONLY=1 DB_UPDATE=0 LINE=0 BUY=0 PROD_CHANGE=0",flush=True)

    periods=("ALL","TRAIN","VALID","TEST","OOS1","OOS2")
    trans=("BOTH","BASE_ONLY","MOTOR2_ONLY")
    stats={n:{p:{t:st() for t in trans} for p in periods} for n,_,_ in CONFIGS}
    venues={n:{t:defaultdict(st) for t in trans[1:]} for n,_,_ in CONFIGS}
    race_nos={n:{t:defaultdict(st) for t in trans[1:]} for n,_,_ in CONFIGS}
    buckets={n:{t:defaultdict(st) for t in trans[1:]} for n,_,_ in CONFIGS}
    weights={0.0}
    for _,l,m in CONFIGS: weights.update((l,m))
    processed=se=sm=sr=so=0

    for ms in bt.month_starts(START_DATE,END_DATE):
        races,entries,results,odds_rows=fetch_month(ms,bt.next_month_start(ms))
        eb=defaultdict(list)
        for e in entries: eb[str(e.get("race_id") or "")].append(e)
        rb={}
        for r in results:
            rid=str(r.get("race_id") or ""); t=bt.norm_ticket(r.get("trifecta_ticket")); p=bt.si(r.get("trifecta_payout_yen"),0)
            if rid and t and p>0: rb[rid]=(t,p)
        ob=defaultdict(dict)
        for o in odds_rows:
            rid=str(o.get("race_id") or ""); t=bt.norm_ticket(o.get("ticket")); odd=bt.sf(o.get("odds"),None)
            if rid and t and odd is not None and odd>0: ob[rid][t]=float(odd)

        for race in races:
            if MAX_RACES and processed>=MAX_RACES: break
            rid=str(race.get("race_id") or ""); ds=str(race.get("race_date") or "")[:10]
            if rid not in rb: sr+=1; continue
            ent=eb.get(rid,[])
            if len(ent)!=6 or {bt.si(e.get("lane")) for e in ent}!={1,2,3,4,5,6}: se+=1; continue
            if sum(bt.valid_motor2(e.get("motor_place2_rate")) is not None for e in ent)!=6: sm+=1; continue
            odds=ob.get(rid,{})
            if not bt.validate_odds(odds): so+=1; continue

            venue=str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            rno=bt.si(race.get("race_no"),0); win,payout=rb[rid]
            market=bt.rank_map(odds,reverse=False)
            rw={w:bt.rank_map(bt.ticket_probs(ent,venue,w),reverse=True) for w in sorted(weights)}
            base_low={t for t,o in odds.items() if bt.is_low(rw[0.0][t],market[t],float(o))}
            base_mid={t for t,o in odds.items() if bt.is_mid(t,rw[0.0][t],market[t],float(o))}
            base=base_low|base_mid; pp=bt.period(ds); mr=motor_rank_map(ent)

            for name,lw,mw in CONFIGS:
                ml={t for t,o in odds.items() if bt.is_low(rw[lw][t],market[t],float(o))}
                mm={t for t,o in odds.items() if bt.is_mid(t,rw[mw][t],market[t],float(o))}
                motor=ml|mm
                for t in base|motor:
                    b=t in base; m=t in motor
                    tr="BOTH" if b and m else "BASE_ONLY" if b else "MOTOR2_ONLY"
                    hit=t==win
                    add(stats[name]["ALL"][tr],hit,payout); add(stats[name][pp][tr],hit,payout)
                    if tr!="BOTH":
                        add(venues[name][tr][venue],hit,payout); add(race_nos[name][tr][rno],hit,payout); add(buckets[name][tr][bucket(t,mr)],hit,payout)

            processed+=1
            if processed%PROGRESS_EVERY==0: print(f"PROGRESS processed={processed} race_id={rid}",flush=True)
        if MAX_RACES and processed>=MAX_RACES: break

    print("\n=== TRANSITION SUMMARY ===",flush=True)
    for name,lw,mw in CONFIGS:
        print(f"\n### CONFIG {name} LOW={lw:.2f} MID={mw:.2f}",flush=True)
        for p in periods:
            print(f"[{p}]",flush=True)
            for tr in trans:
                s=stats[name][p][tr]
                print(f"  {tr}: bets={s['bets']} hits={s['hits']} hit_rate={hr(s):.3f}% ROI={roi(s):.2f}% profit={s['return']-s['investment']}",flush=True)
        for tr in ("BASE_ONLY","MOTOR2_ONLY"):
            print(f"--- {tr} TOP VENUES ---",flush=True)
            for v,s in sorted(venues[name][tr].items(),key=lambda kv:(-kv[1]["bets"],kv[0]))[:12]:
                print(f"  venue={v} bets={s['bets']} hits={s['hits']} ROI={roi(s):.2f}%",flush=True)
            print(f"--- {tr} BY RACE_NO ---",flush=True)
            for r in sorted(race_nos[name][tr]):
                s=race_nos[name][tr][r]
                print(f"  R{r:02d}: bets={s['bets']} hits={s['hits']} ROI={roi(s):.2f}%",flush=True)
            print(f"--- {tr} BY MOTOR-RANK BUCKET ---",flush=True)
            for b in ("HAS_M1","HAS_M2","HAS_M3","NO_TOP3","UNKNOWN"):
                s=buckets[name][tr].get(b,st())
                print(f"  {b}: bets={s['bets']} hits={s['hits']} ROI={roi(s):.2f}%",flush=True)

    print("\n=== AUDIT ===",flush=True)
    print(f"processed={processed}",flush=True)
    print(f"skipped_entries={se}",flush=True)
    print(f"skipped_motor2={sm}",flush=True)
    print(f"skipped_result={sr}",flush=True)
    print(f"skipped_odds={so}",flush=True)
    print("RESULT=PASS",flush=True)

if __name__=="__main__":
    main()