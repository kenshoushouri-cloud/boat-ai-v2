# -*- coding: utf-8 -*-
from __future__ import annotations
import math, os, re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
from db_pg import fetch_all

JST=timezone(timedelta(hours=9))
START=os.getenv("ANALYZE_START_DATE","2026-06-01")
END=os.getenv("ANALYZE_END_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
LIMIT=max(1,int(os.getenv("AB_SAMPLE_LIMIT","30")))
TEMP=2.2
CW={1:.15,2:.55,3:1.15,4:1.55}
VCB={"01":{1:2.762,2:2.747,3:3.385,4:4.070,5:3.537,6:2.343},"06":{1:2.932,2:3.401,3:3.571,4:3.195,5:2.694,6:2.403},"12":{1:3.249,2:3.344,3:2.957,4:2.824,5:2.313,6:1.553},"18":{1:3.509,2:3.116,3:2.908,4:2.648,5:1.380,6:1.355},"24":{1:3.561,2:2.880,3:2.659,4:2.267,5:2.049,6:1.314}}
DCB={1:3.2,2:3.1,3:3.1,4:3.0,5:2.4,6:1.8}

def sf(v,d=0.0):
    try:return float(str(v).replace(",","")) if v not in (None,"") else d
    except:return d
def si(v,d=0):
    try:return int(float(str(v).replace(",",""))) if v not in (None,"") else d
    except:return d
def nt(v):
    s=str(v or "")
    a=re.findall(r"(?<!\d)([1-6])(?!\d)",s)
    if len(a)>=3:return f"{a[0]}-{a[1]}-{a[2]}"
    s=re.sub(r"\D","",s)
    return f"{s[0]}-{s[1]}-{s[2]}" if len(s)>=3 and all(c in "123456" for c in s[:3]) else ""
def rel(n): return .2 if n<=5 else .5 if n<=15 else .8 if n<=30 else 1.0
def shrink(x,p,n): return x*rel(n)+p*(1-rel(n))
def strength(e,l,v,m,b):
    st=sf(e.get("avg_st"),.18); ss=max(0,min(1,(.24-st)/.12))
    return CW.get(si(e.get("racer_class"),2),.55)+sf(e.get("national_win_rate"))*.16+sf(e.get("national_place2_rate"),32)/100*.9+sf(e.get("local_place2_rate"),30)/100*.55+m/100*.45+b/100*.25+ss*.35+VCB.get(v,DCB).get(l,DCB[l])*.22
def probs(es,v,mode,cnt):
    by={si(e.get("lane")):e for e in es}
    if len(by)!=6:return {}
    raw={}
    for l in range(1,7):
        e=by[l]
        if mode=="fixed": m,b=33.,34.
        else:
            mn=str(e.get("motor_no") or ""); bn=str(e.get("boat_no") or "")
            m=shrink(sf(e.get("motor_place2_rate"),33),33,cnt.get(("m",v,mn),0))
            b=shrink(sf(e.get("boat_place2_rate"),34),34,cnt.get(("b",v,bn),0))
        raw[l]=strength(e,l,v,m,b)
    w={l:math.exp(raw[l]/TEMP) for l in raw}; total=sum(w.values()); out={}
    for a in range(1,7):
        pa=w[a]/total; tb=total-w[a]
        for b in range(1,7):
            if b==a:continue
            pb=w[b]/tb; tc=tb-w[b]
            for c in range(1,7):
                if c in (a,b):continue
                out[f"{a}-{b}-{c}"]=pa*pb*w[c]/tc
    return out
def ranks(p): return {t:i for i,(t,_) in enumerate(sorted(p.items(),key=lambda x:x[1],reverse=True),1)}
def mranks(o): return {t:i for i,(t,_) in enumerate(sorted(o.items(),key=lambda x:x[1]),1)}

def main():
    if not os.getenv("DATABASE_URL"): raise RuntimeError("DATABASE_URL ãå¿è¦ã§ãã")
    print("â compare_motor_boat_ab_pg.py VERSION 2026-07-15")
    print(f"PERIOD={START}..{END}")
    er=fetch_all("""select r.race_id,r.race_date,coalesce(r.venue_id,r.venue_code) venue_id,r.race_no,e.* from v2_races r join v2_race_entries e on e.race_id=r.race_id where r.race_date between %s and %s order by r.race_date,r.race_id,e.lane""",(START,END))
    endx=(datetime.strptime(END,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y%m%d")
    rr=fetch_all("select race_id,first_lane,second_lane,third_lane,trifecta_ticket from v2_results where race_id >= %s and race_id < %s",(START.replace("-",""),endx))
    oo=fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s",(START.replace("-",""),endx))
    races={}
    for r in er:
        rid=str(r["race_id"]); x=races.setdefault(rid,{"date":str(r["race_date"]),"venue":str(r["venue_id"]).zfill(2),"race_no":si(r["race_no"]),"entries":[]}); x["entries"].append(r)
    results={}
    for r in rr:
        a,b,c=si(r.get("first_lane")),si(r.get("second_lane")),si(r.get("third_lane"))
        t=f"{a}-{b}-{c}" if all(1<=x<=6 for x in (a,b,c)) else nt(r.get("trifecta_ticket"))
        if t:results[str(r["race_id"])]=t
    odds=defaultdict(dict)
    for r in oo:
        t=nt(r.get("ticket")); o=sf(r.get("odds"))
        if t and o>0:odds[str(r["race_id"])][t]=o
    print(f"loaded races={len(races)} results={len(results)} odds_races={len(odds)}")
    cnt=Counter(); sfixed=Counter(); sreal=Counter(); shift=Counter(); bf=br=chg=0; samples=[]; analyzed=0
    for rid,x in sorted(races.items(),key=lambda z:(z[1]["date"],z[0])):
        es=x["entries"]; o=odds.get(rid,{}); rt=results.get(rid); v=x["venue"]
        if len(es)==6 and len(o)>=100 and rt:
            pf,pr=probs(es,v,"fixed",cnt),probs(es,v,"real",cnt); rf,rrk=ranks(pf),ranks(pr); mf=mranks(o)
            a,b=rf.get(rt,999),rrk.get(rt,999); analyzed+=1
            for rank,s in ((a,sfixed),(b,sreal)):
                s["n"]+=1;s["sum"]+=rank
                for k in (1,3,5,10,20): s[f"t{k}"]+=int(rank<=k)
            d=a-b; shift["improved"]+=int(d>0);shift["worsened"]+=int(d<0);shift["same"]+=int(d==0);shift["net"]+=d
            fav=min(o,key=o.get); fo=o[fav]
            xbf=11<=rf.get(fav,999)<=20 and mf.get(fav)==1 and 3<=fo<5 and x["race_no"]<=9
            xbr=11<=rrk.get(fav,999)<=20 and mf.get(fav)==1 and 3<=fo<5 and x["race_no"]<=9
            bf+=int(xbf);br+=int(xbr);chg+=int(xbf!=xbr)
            if len(samples)<LIMIT and abs(d)>=5:samples.append((rid,rt,a,b,d,fav,fo,xbf,xbr))
        for e in es:
            mn=str(e.get("motor_no") or "");bn=str(e.get("boat_no") or "")
            if mn:cnt[("m",v,mn)]+=1
            if bn:cnt[("b",v,bn)]+=1
    def show(name,s):
        n=s["n"];print(f"\n{name}\n  races={n} avg_result_prob_rank={(s['sum']/n if n else 0):.2f}")
        for k in (1,3,5,10,20):print(f"  result_in_top{k}={s[f't{k}']} ({(s[f't{k}']/n*100 if n else 0):.2f}%)")
    print(f"analyzed_races={analyzed}");show("FIXED motor=33 boat=34",sfixed);show("REAL shrunk motor/boat",sreal)
    print(f"\nRANK SHIFT\n  improved={shift['improved']} worsened={shift['worsened']} same={shift['same']} net_rank_gain={shift['net']}")
    print(f"\nB-RANK CONDITION\n  fixed_candidates={bf}\n  real_candidates={br}\n  changed_candidate_status={chg}")
    print("\nLARGE SHIFT SAMPLES")
    for x in samples:print(" ",x)
    print("=== motor/boat A/B comparison finished ===")
if __name__=="__main__":main()