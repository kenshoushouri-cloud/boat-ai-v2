# -*- coding: utf-8 -*-
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

JST=timezone(timedelta(hours=9))
START=os.getenv("BT_START_DATE","2025-07-01")
VALID=os.getenv("BT_VALID_START_DATE","2026-03-01")
TEST=os.getenv("BT_TEST_START_DATE","2026-06-01")
END=os.getenv("BT_END_DATE",datetime.now(JST).strftime("%Y-%m-%d"))
MINP=int(os.getenv("BT3_MIN_PERIOD_CANDIDATES","20"))
MINM=int(os.getenv("BT3_MIN_MONTH_CANDIDATES","5"))
TOP=int(os.getenv("BT3_TOP_N","50"))

BASES=[
{"id":"B1","pr":(11,25),"mr":(2,5),"od":(3.,6.),"mode":"ev"},
{"id":"B2","pr":(11,25),"mr":(2,5),"od":(3.,6.),"mode":"prob"},
{"id":"B3","pr":(11,20),"mr":(2,5),"od":(3.,6.),"mode":"ev"},
{"id":"B4","pr":(11,20),"mr":(2,5),"od":(3.,6.),"mode":"prob"}]
STRATS=["BASE_ALL","EXCLUDE_R01_03","EXCLUDE_R01_06","R07_12","R07_09","R10_12","R07_09_PLUS_R10","CATEGORY_OTHER","CATEGORY_OTHER_R07_12"]

def sf(x,d=0.):
    try:return float(x)
    except:return d
def si(x,d=0):
    try:return int(float(x))
    except:return d
def nd(s): return (datetime.strptime(s,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y-%m-%d")
def months(a,b):
    d=datetime.strptime(a[:7]+"-01","%Y-%m-%d"); e=datetime.strptime(b[:7]+"-01","%Y-%m-%d")
    while d<=e:
        yield d.strftime("%Y-%m-01")
        d=d.replace(year=d.year+1,month=1) if d.month==12 else d.replace(month=d.month+1)
def mend(s):
    d=datetime.strptime(s,"%Y-%m-%d")
    d=d.replace(year=d.year+1,month=1) if d.month==12 else d.replace(month=d.month+1)
    return d.strftime("%Y-%m-%d")
def period(d): return "TRAIN" if d<VALID else ("VALID" if d<TEST else "TEST")
def cat(n):
    n=n or ""; l=n.lower()
    if "ãªã¼ã«ã¬ãã£ã¼ã¹" in n or "all ladies" in l:return "all_ladies"
    if "ã´ã£ã¼ãã¹" in n or "venus" in l:return "venus"
    if "ã«ã¼ã­ã¼" in n or "rookie" in l:return "rookie"
    if "ãã¹ã¿ã¼ãº" in n or "masters" in l:return "masters"
    if "ã¬ãã£ã¼ã¹" in n or "å¥³å­" in n or "ladies" in l:return "ladies_other"
    if any(x.lower() in l for x in ("SG","G1","Gâ ","G2","Gâ¡","G3","Gâ¢")):return "G1_like"
    return "category_other"
def smatch(s,r,c):
    return {"BASE_ALL":True,"EXCLUDE_R01_03":r>=4,"EXCLUDE_R01_06":r>=7,"R07_12":7<=r<=12,
    "R07_09":7<=r<=9,"R10_12":10<=r<=12,"R07_09_PLUS_R10":7<=r<=10,
    "CATEGORY_OTHER":c=="category_other","CATEGORY_OTHER_R07_12":c=="category_other" and 7<=r<=12}[s]
def stat():return {"n":0,"h":0,"ret":0,"mx":0,"seq":[]}
def add(s,hit,pay):
    s["n"]+=1;s["seq"].append(pay-100 if hit else -100)
    if hit:s["h"]+=1;s["ret"]+=pay;s["mx"]=max(s["mx"],pay)
def lose(seq):
    c=m=0
    for x in seq:
        if x<0:c+=1;m=max(m,c)
        else:c=0
    return m
def dd(seq):
    e=p=w=0
    for x in seq:e+=x;p=max(p,e);w=max(w,p-e)
    return w
def met(s):
    n=s["n"]; inv=n*100; ret=s["ret"]; pr=ret-inv
    return {"n":n,"h":s["h"],"hr":s["h"]/n*100 if n else 0,"roi":ret/inv*100 if inv else 0,
    "profit":pr,"p100":pr/n*100 if n else 0,"single":s["mx"]/ret*100 if ret else 0,"lose":lose(s["seq"]),"dd":dd(s["seq"])}
def fetch(ms,mx):
    a=max(START,ms); b=min(nd(END),mx)
    if a>=b:return [],[],[],[]
    ra,rb=a.replace("-",""),b.replace("-","")
    r=fetch_all("select * from v2_races where race_date >= %s and race_date < %s order by race_date,venue_id,race_no",(a,b))
    e=fetch_all("select * from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane",(ra,rb))
    o=fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s order by race_id,ticket",(ra,rb))
    z=fetch_all("select race_id,trifecta_ticket,trifecta_payout_yen from v2_results where race_id >= %s and race_id < %s",(ra,rb))
    return r,e,o,z
def best(rows,b):
    a=[x for x in rows if b["pr"][0]<=si(x.get("prob_rank"),999)<=b["pr"][1] and b["mr"][0]<=si(x.get("market_rank"),999)<=b["mr"][1] and b["od"][0]<=sf(x.get("odds"))<b["od"][1]]
    if not a:return None
    key=(lambda x:(sf(x.get("raw_ev")),sf(x.get("prob")))) if b["mode"]=="ev" else (lambda x:(sf(x.get("prob")),sf(x.get("raw_ev"))))
    return max(a,key=key)

def main():
    if not os.getenv("DATABASE_URL"):raise RuntimeError("DATABASE_URL ãå¿è¦ã§ã")
    print("â analyze_candidate_walkforward_phase3_pg.py VERSION 2026-08-13 operational-portfolio-v1")
    print(f"PERIOD={START}..{END} VALID={VALID} TEST={TEST}")
    print("READ ONLY: DBæ´æ°ã»LINEéç¥ã»æ¬çªå¤æ´ãªã")
    A=defaultdict(stat); M=defaultdict(stat)
    for ms in months(START,END):
        races,er,orr,rr=fetch(ms,mend(ms)); eb=defaultdict(list); ob=defaultdict(dict); rb={}
        for x in er:eb[str(x.get("race_id") or "")].append(x)
        for x in orr:
            rid=str(x.get("race_id") or ""); t=v24._norm_ticket(x.get("ticket")); od=sf(x.get("odds"))
            if rid and t and od>0:ob[rid][t]=od
        for x in rr:
            rid=str(x.get("race_id") or ""); t=v24._norm_ticket(x.get("trifecta_ticket")); pay=si(x.get("trifecta_payout_yen"))
            if rid and t and pay>0:rb[rid]=(t,pay)
        ready=0
        for race in races:
            rid=str(race.get("race_id") or ""); entries=eb.get(rid,[]); odds=ob.get(rid,{})
            if len(v24._entry_by_lane(entries))!=6 or rid not in rb:continue
            ok,_=v24._validate_odds_snapshot(odds)
            if not ok:continue
            ready+=1; d=str(race.get("race_date") or "")[:10]; pe=period(d)
            v=str(race.get("venue_id") or race.get("venue_code") or "").zfill(2); rn=si(race.get("race_no")); c=cat(str(race.get("race_name") or ""))
            ranked=v24._rank_candidates(entries,v,odds); rt,pay=rb[rid]
            for b in BASES:
                sel=best(ranked,b)
                if not sel:continue
                hit=str(sel.get("ticket") or "")==rt
                for s in STRATS:
                    if smatch(s,rn,c):
                        add(A[(b["id"],s,pe)],hit,pay); add(M[(b["id"],s,d[:7])],hit,pay)
        print(f"month={ms[:7]} races={len(races)} ready={ready}")
    rows=[]
    for b in BASES:
        for s in STRATS:
            t,v,x=[met(A[(b["id"],s,p)]) for p in ("TRAIN","VALID","TEST")]
            if min(t["n"],v["n"],x["n"])<MINP:continue
            ms=[]
            for m in sorted({k[2] for k in M if k[0]==b["id"] and k[1]==s}):
                mm=met(M[(b["id"],s,m)])
                if mm["n"]>=MINM:ms.append((m,mm))
            plus=sum(1 for _,m in ms if m["profit"]>0)/len(ms)*100 if ms else 0
            worst=min(t["roi"],v["roi"],x["roi"]); spread=max(t["roi"],v["roi"],x["roi"])-worst
            totaln=t["n"]+v["n"]+x["n"]; totalp=t["profit"]+v["profit"]+x["profit"]
            score=worst+plus*.2+min(totaln/10,25)+min(totalp/2500,25)-spread*.15-x["dd"]/1000-x["lose"]*.35
            rows.append((score,b,s,t,v,x,plus,len(ms),worst,spread,totaln,totalp,ms))
    rows.sort(reverse=True,key=lambda r:(r[0],r[8],r[5]["roi"],r[5]["profit"],r[5]["n"]))
    print("\\n=== operational strategy ranking ===")
    for i,r in enumerate(rows[:TOP],1):
        score,b,s,t,v,x,plus,nm,worst,spread,totaln,totalp,ms=r
        print(f"{i:03d}. {b['id']} / {s} score={score:.2f}")
        print(f"     TRAIN n={t['n']} hits={t['h']} hit_rate={t['hr']:.2f}% ROI={t['roi']:.2f}% profit={t['profit']}")
        print(f"     VALID n={v['n']} hits={v['h']} hit_rate={v['hr']:.2f}% ROI={v['roi']:.2f}% profit={v['profit']}")
        print(f"     TEST n={x['n']} hits={x['h']} hit_rate={x['hr']:.2f}% ROI={x['roi']:.2f}% profit={x['profit']} profit/100cand={x['p100']:.0f} lose_streak={x['lose']} maxDD={x['dd']}")
        print(f"     plus_months={plus:.1f}%/{nm} worstROI={worst:.2f}% spread={spread:.2f}pt total_n={totaln} total_profit={totalp}")
    print("\\n=== top strategy monthly details ===")
    for r in rows[:10]:
        _,b,s,_,_,_,_,_,_,_,_,_,ms=r; print(f"\\n{b['id']} / {s}")
        for m,x in ms:print(f"{m} n={x['n']} hits={x['h']} hit_rate={x['hr']:.1f}% ROI={x['roi']:.1f}% profit={x['profit']}")
    print("\\n=== deployment shortlist ===")
    sh=[r for r in rows if r[3]["roi"]>=100 and r[4]["roi"]>=100 and r[5]["roi"]>=100 and r[5]["profit"]>0 and r[6]>=50 and r[5]["n"]>=20]
    if not sh:print("ç¾åºæºã§ã¯æ¬çªåè£ãªã")
    for i,r in enumerate(sh[:20],1):
        _,b,s,t,v,x,plus,_,_,_,_,_,_=r
        print(f"{i:02d}. {b['id']} / {s} TRAIN={t['roi']:.1f}% VALID={v['roi']:.1f}% TEST={x['roi']:.1f}% TEST_n={x['n']} hit_rate={x['hr']:.1f}% plus_months={plus:.1f}% maxDD={x['dd']}")
    print("\\n=== phase3 analysis finished ===")
if __name__=="__main__":main()