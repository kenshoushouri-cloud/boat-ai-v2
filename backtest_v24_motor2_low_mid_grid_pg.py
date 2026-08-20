# -*- coding: utf-8 -*-
from __future__ import annotations

import itertools, math, os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from db_pg import fetch_all

VERSION = "2026-08-20 v24-motor2-low-mid-grid-v1"
START_DATE = os.getenv("MOTOR2_GRID_START_DATE", "2025-07-01").strip()
END_DATE = os.getenv("MOTOR2_GRID_END_DATE", "2026-08-19").strip()
UNIT_YEN = max(1, int(os.getenv("MOTOR2_GRID_UNIT_YEN", "100")))
PROGRESS_EVERY = max(1, int(os.getenv("MOTOR2_GRID_PROGRESS_EVERY", "5000")))
MAX_RACES = max(0, int(os.getenv("MOTOR2_GRID_MAX_RACES", "0")))
REQUIRE_COMPLETE_MOTOR2 = os.getenv("MOTOR2_GRID_REQUIRE_COMPLETE_MOTOR2", "1").strip().lower() not in {"0","false","no","off"}
LOW_WEIGHTS = sorted({round(float(x.strip()),6) for x in os.getenv("MOTOR2_GRID_LOW_WEIGHTS","0,0.10,0.20,0.30,0.40,0.45,0.50,0.60,0.70,0.80").split(",") if x.strip()})
MID_WEIGHTS = sorted({round(float(x.strip()),6) for x in os.getenv("MOTOR2_GRID_MID_WEIGHTS","0,0.05,0.10,0.15,0.20,0.25,0.30,0.40").split(",") if x.strip()})
if 0.0 not in LOW_WEIGHTS: LOW_WEIGHTS=[0.0]+LOW_WEIGHTS
if 0.0 not in MID_WEIGHTS: MID_WEIGHTS=[0.0]+MID_WEIGHTS

PROB_TEMP=2.20
CLASS_WEIGHT={1:.15,2:.55,3:1.15,4:1.55}
VENUE_COURSE_BIAS={
"01":{1:2.762,2:2.747,3:3.385,4:4.070,5:3.537,6:2.343},
"06":{1:2.932,2:3.401,3:3.571,4:3.195,5:2.694,6:2.403},
"12":{1:3.249,2:3.344,3:2.957,4:2.824,5:2.313,6:1.553},
"18":{1:3.509,2:3.116,3:2.908,4:2.648,5:1.380,6:1.355},
"24":{1:3.561,2:2.880,3:2.659,4:2.267,5:2.049,6:1.314}}
DEFAULT_COURSE_BIAS={1:3.20,2:3.10,3:3.10,4:3.00,5:2.40,6:1.80}
ALL_LANES={1,2,3,4,5,6}


def sf(v,d=None):
    try:return float(v) if v not in (None,"") else d
    except:return d

def si(v,d=0):
    try:return int(float(v)) if v not in (None,"") else d
    except:return d

def period(ds):
    if ds<"2026-03-01":return "TRAIN"
    if ds<"2026-05-01":return "VALID"
    if ds<"2026-07-01":return "TEST"
    if ds<"2026-08-01":return "OOS1"
    return "OOS2"

def month_starts(a,b):
    d=datetime.strptime(a[:7]+"-01","%Y-%m-%d"); e=datetime.strptime(b[:7]+"-01","%Y-%m-%d")
    while d<=e:
        yield d.strftime("%Y-%m-%d")
        d=d.replace(year=d.year+1,month=1) if d.month==12 else d.replace(month=d.month+1)

def next_month(s):
    d=datetime.strptime(s,"%Y-%m-%d")
    d=d.replace(year=d.year+1,month=1) if d.month==12 else d.replace(month=d.month+1)
    return d.strftime("%Y-%m-%d")

def next_day(s): return (datetime.strptime(s,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y-%m-%d")

def norm_ticket(v):
    s=str(v or "").strip(); p=s.split("-")
    if len(p)!=3:return ""
    try:x=[int(i) for i in p]
    except:return ""
    return f"{x[0]}-{x[1]}-{x[2]}" if all(i in ALL_LANES for i in x) and len(set(x))==3 else ""

def validate_odds(o):
    active=set()
    for t in o:
        nt=norm_ticket(t)
        if not nt:return False
        active.update(map(int,nt.split("-")))
    return 4<=len(active)<=6 and set(o)=={f"{a}-{b}-{c}" for a,b,c in itertools.permutations(sorted(active),3)}

def valid_m2(v):
    x=sf(v,None)
    return x if x is not None and 0<=x<=100 else None

def raw(e,lane,venue,mw):
    cls=si(e.get("racer_class"),2); cw=CLASS_WEIGHT.get(cls,.55)
    wr=sf(e.get("national_win_rate"),0) or 0
    n2=sf(e.get("national_place2_rate"),32); n2=32 if n2 is None else n2
    l2=sf(e.get("local_place2_rate"),30); l2=30 if l2 is None else l2
    st=sf(e.get("avg_st"),.18); st=.18 if st is None else st
    m2=valid_m2(e.get("motor_place2_rate")); m2=33 if m2 is None else m2
    cb=VENUE_COURSE_BIAS.get(venue,DEFAULT_COURSE_BIAS).get(lane,DEFAULT_COURSE_BIAS[lane])
    ss=max(0,min(1,(.24-st)/.12))
    return cw+wr*.16+(n2/100)*.90+(l2/100)*.55+(m2/100)*mw+(34/100)*.25+ss*.35+cb*.22

def probs(entries,venue,mw):
    by={si(e.get("lane")):e for e in entries}
    r={i:raw(by[i],i,venue,mw) for i in range(1,7)}
    w={i:math.exp(r[i]/PROB_TEMP) for i in range(1,7)}; total=sum(w.values()); out={}
    for a in range(1,7):
        pa=w[a]/total; tb=total-w[a]
        for b in range(1,7):
            if b==a:continue
            pb=w[b]/tb; tc=tb-w[b]
            for c in range(1,7):
                if c in (a,b):continue
                out[f"{a}-{b}-{c}"]=pa*pb*(w[c]/tc)
    return out

def ranks(d,reverse=True):
    key=(lambda kv:(-kv[1],kv[0])) if reverse else (lambda kv:(kv[1],kv[0]))
    return {t:i for i,(t,_) in enumerate(sorted(d.items(),key=key),1)}

def is_low(pr,mr,odd): return 11<=pr<=20 and mr==1 and 3<=odd<5

def is_mid(t,pr,mr,odd): return 4<=pr<=5 and 21<=mr<=30 and 30<=odd<50 and not t.startswith("1-")

def stat_new(): return {"bets":0,"hits":0,"inv":0,"ret":0,"lb":0,"lh":0,"lr":0,"mb":0,"mh":0,"mr":0}

def add(s,k,hit,pay):
    s["bets"]+=1; s["inv"]+=UNIT_YEN; s["lb" if k=="L" else "mb"]+=1
    if hit:
        s["hits"]+=1; s["ret"]+=pay; s["lh" if k=="L" else "mh"]+=1; s["lr" if k=="L" else "mr"]+=pay

def roi(ret,inv): return ret/inv*100 if inv else 0.0

def fetch_month(ms,mx):
    a=max(START_DATE,ms); b=min(next_day(END_DATE),mx)
    if a>=b:return [],[],[],[]
    ra=a.replace("-",""); rb=b.replace("-","")
    races=fetch_all("""select race_id,race_date,venue_id,venue_code,race_no from v2_races where race_date >= %s and race_date < %s order by race_date,venue_id,race_no""",(a,b))
    entries=fetch_all("""select race_id,lane,racer_class,national_win_rate,national_place2_rate,local_place2_rate,avg_st,motor_place2_rate from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane""",(ra,rb))
    results=fetch_all("""select race_id,trifecta_ticket,trifecta_payout_yen from v2_results where race_date >= %s and race_date < %s and result_status='official' and race_status='official' and trifecta_ticket is not null and trifecta_payout_yen>0""",(a,b))
    odds=fetch_all("""select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s and odds>0 order by race_id,ticket""",(ra,rb))
    return races,entries,results,odds

def main():
    if not os.getenv("DATABASE_URL"): raise RuntimeError("DATABASE_URL ãå¿è¦ã§ãã")
    combos=[(l,m) for l in LOW_WEIGHTS for m in MID_WEIGHTS]
    print(f"â backtest_v24_motor2_low_mid_grid_pg.py VERSION {VERSION}",flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE} LOW={LOW_WEIGHTS} MID={MID_WEIGHTS} COMBINATIONS={len(combos)}",flush=True)
    print("READ_ONLY=1 DB_UPDATE=0 LINE=0 BUY=0 PROD_CHANGE=0",flush=True)
    overall={c:stat_new() for c in combos}
    bp={p:{c:stat_new() for c in combos} for p in ("TRAIN","VALID","TEST","OOS1","OOS2")}
    processed=se=sm=sr=so=0

    for ms in month_starts(START_DATE,END_DATE):
        races,entries,results,orows=fetch_month(ms,next_month(ms))
        eb=defaultdict(list)
        for e in entries: eb[str(e.get("race_id") or "")].append(e)
        rb={}
        for r in results:
            t=norm_ticket(r.get("trifecta_ticket")); pay=si(r.get("trifecta_payout_yen"),0)
            if t and pay>0: rb[str(r.get("race_id"))]=(t,pay)
        ob=defaultdict(dict)
        for o in orows:
            t=norm_ticket(o.get("ticket")); odd=sf(o.get("odds"),None)
            if t and odd and odd>0: ob[str(o.get("race_id"))][t]=float(odd)
        month_processed=0
        for race in races:
            if MAX_RACES and processed>=MAX_RACES: break
            rid=str(race.get("race_id") or ""); ds=str(race.get("race_date") or "")[:10]
            if rid not in rb: sr+=1; continue
            ent=eb.get(rid,[])
            if len(ent)!=6 or {si(e.get("lane")) for e in ent}!={1,2,3,4,5,6}: se+=1; continue
            if REQUIRE_COMPLETE_MOTOR2 and sum(valid_m2(e.get("motor_place2_rate")) is not None for e in ent)!=6: sm+=1; continue
            odds=ob.get(rid,{})
            if not validate_odds(odds): so+=1; continue
            venue=str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            win,pay=rb[rid]; mr=ranks(odds,False)
            allw=sorted(set(LOW_WEIGHTS+MID_WEIGHTS))
            rw={w:ranks(probs(ent,venue,w),True) for w in allw}
            lows={w:{t for t,o in odds.items() if is_low(rw[w][t],mr[t],float(o))} for w in LOW_WEIGHTS}
            mids={w:{t for t,o in odds.items() if is_mid(t,rw[w][t],mr[t],float(o))} for w in MID_WEIGHTS}
            pp=period(ds)
            for c in combos:
                lw,mw=c; used=set()
                for t in lows[lw]:
                    used.add(t); add(overall[c],"L",t==win,pay); add(bp[pp][c],"L",t==win,pay)
                for t in mids[mw]:
                    if t in used: continue
                    add(overall[c],"M",t==win,pay); add(bp[pp][c],"M",t==win,pay)
            processed+=1; month_processed+=1
            if processed%PROGRESS_EVERY==0: print(f"PROGRESS processed={processed} race_id={rid}",flush=True)
        print(f"month={ms[:7]} processed={month_processed}",flush=True)
        if MAX_RACES and processed>=MAX_RACES: break

    base=(0.0,0.0); base_roi=roi(overall[base]["ret"],overall[base]["inv"])
    ranking=[]
    for c,s in overall.items():
        hold=[roi(bp[p][c]["ret"],bp[p][c]["inv"]) for p in ("VALID","TEST","OOS1")]
        ranking.append((min(hold),sum(hold)/3,roi(s["ret"],s["inv"]),c))
    ranking.sort(reverse=True)

    print("=== GRID OVERALL TOP 20 ===",flush=True)
    for i,(_,hav,r,c) in enumerate(ranking[:20],1):
        s=overall[c]; lw,mw=c
        print(f"{i:02d}. LOW={lw:.2f} MID={mw:.2f} bets={s['bets']} hits={s['hits']} ROI={r:.2f}% delta_vs_base={r-base_roi:+.2f}pt LOW_ROI={roi(s['lr'],s['lb']*UNIT_YEN):.2f}% MID_ROI={roi(s['mr'],s['mb']*UNIT_YEN):.2f}% holdout_avg={hav:.2f}%",flush=True)

    print("=== PERIOD STABILITY TOP 10 ===",flush=True)
    for i,(_,_,_,c) in enumerate(ranking[:10],1):
        print(f"[{i:02d}] LOW={c[0]:.2f} MID={c[1]:.2f}",flush=True)
        for pn in ("TRAIN","VALID","TEST","OOS1","OOS2"):
            s=bp[pn][c]; b=bp[pn][base]
            rr=roi(s["ret"],s["inv"]); br=roi(b["ret"],b["inv"])
            print(f"  {pn}: bets={s['bets']} hits={s['hits']} ROI={rr:.2f}% delta_vs_base={rr-br:+.2f}pt",flush=True)

    print("=== AUDIT ===",flush=True)
    print(f"processed={processed}",flush=True)
    print(f"skipped_entries={se}",flush=True)
    print(f"skipped_motor2={sm}",flush=True)
    print(f"skipped_result={sr}",flush=True)
    print(f"skipped_odds={so}",flush=True)
    print(f"combinations={len(combos)}",flush=True)
    print("RESULT=PASS",flush=True)

if __name__=="__main__": main()