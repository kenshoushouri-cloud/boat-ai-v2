# -*- coding: utf-8 -*-
"""V5 B11A: wind-speed x wave-height incremental over B1 lane baseline."""
from __future__ import annotations
import json,math,os
from collections import Counter,defaultdict
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
from typing import Any
from db_pg import fetch_all

START=os.getenv("START_DATE","2025-07-01")
END=os.getenv("END_DATE","2026-10-05")
LABEL="historical"; EPS=1e-12; ALPHA=1.0

def iso(v):
    if isinstance(v,datetime):return v.date().isoformat()
    if isinstance(v,date):return v.isoformat()
    return str(v)
def cols(t):
    return {str(r["column_name"]) for r in fetch_all("select column_name from information_schema.columns where table_schema='public' and table_name=%s",(t,))}
def winexpr(c):
    if "first_lane" in c:return "rs.first_lane::int"
    return "nullif(substring(regexp_replace(rs.trifecta_ticket::text,'[^0-9]','','g') from 1 for 1),'')::int"
def venueexpr(c):
    if "venue_id" in c and "venue_code" in c:return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
    return "lpad(r."+("venue_id" if "venue_id" in c else "venue_code")+"::text,2,'0')"
def keynum(v):
    if v is None:return None
    try:d=Decimal(str(v))
    except (InvalidOperation,ValueError):return None
    return format(d.normalize(),"f") if d.is_finite() else None
def lane_probs(w,n):
    den=n+6*ALPHA
    return [(w[i]+ALPHA)/den for i in range(1,7)]
def score(p,w):
    ll=-math.log(max(p[w-1],EPS));y=[0.0]*6;y[w-1]=1.0
    br=sum((p[i]-y[i])**2 for i in range(6))
    m=max(p);tops=[i+1 for i,x in enumerate(p) if abs(x-m)<1e-15]
    return ll,br,int(len(tops)==1 and tops[0]==w)
def cell(lane,k,starts,wins,prior):
    n=starts[lane][k];w=wins[lane][k]
    return (w+2*prior)/(n+2),n
def adjusted(lane,k,prior,starts,wins):
    vals=[];svars=[]
    for kk,n in starts[lane].items():
        if n<=0:continue
        r,_=cell(lane,kk,starts,wins,prior);vals.append(r);svars.append(max(r*(1-r)/n,EPS))
    tau2=0.0
    if len(vals)>=2:
        m=sum(vals)/len(vals)
        tau2=max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(svars)/len(svars))
    r,n=cell(lane,k,starts,wins,prior)
    if n<=0 or tau2<=0:return prior,n,0.0
    svar=max(r*(1-r)/n,EPS);wt=tau2/(tau2+svar)
    return wt*r+(1-wt)*prior,n,wt

def main():
    rc,xc,wc=cols("v2_races"),cols("v2_results"),cols("v2_realtime_weather_snapshots")
    for f in ("wind_speed_m","wave_height_cm"):
        if f not in wc:raise RuntimeError(f+" unavailable")
    we=winexpr(xc);ve=venueexpr(rc)
    fs=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc:fs.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc:fs.append("coalesce(rs.race_status,'official')='official'")
    races=fetch_all(f"select r.race_id,r.race_date,{ve} venue,{we} winner from v2_races r join v2_results rs on rs.race_id=r.race_id where {' and '.join(fs)} order by r.race_date,r.race_id",(START,END))
    ws=fetch_all("""select w.race_id,r.race_date,w.wind_speed_m,w.wave_height_cm
      from v2_realtime_weather_snapshots w join v2_races r on r.race_id=w.race_id
      where r.race_date between %s and %s and w.snapshot_label=%s
      order by r.race_date,w.race_id,w.snapshot_at""",(START,END,LABEL))
    wb={str(r["race_id"]):int(r["winner"]) for r in races};db={str(r["race_id"]):iso(r["race_date"]) for r in races};vb={str(r["race_id"]):str(r["venue"]) for r in races}
    cond={}
    invalid=0
    for x in ws:
        rid=str(x["race_id"])
        a=keynum(x["wind_speed_m"]);b=keynum(x["wave_height_cm"])
        if a is None or b is None:invalid+=1;continue
        cond[rid]=(a,b)
    days=defaultdict(list);skip=0
    for rid in wb:
        if rid in cond:days[db[rid]].append(rid)
        else:skip+=1
    lw=Counter();gn=0
    starts={i:Counter() for i in range(1,7)};wins={i:Counter() for i in range(1,7)}
    tot={"n":0,"bll":0.0,"bbr":0.0,"bh":0,"cll":0.0,"cbr":0.0,"ch":0,"ws":0.0,"wn":0,"seen":0}
    pv=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})
    for day in sorted(days):
        bp=lane_probs(lw,gn);day_lw=Counter();ds={i:Counter() for i in range(1,7)};dw={i:Counter() for i in range(1,7)}
        for rid in days[day]:
            k=cond[rid];raw=[]
            for lane in range(1,7):
                q,n,wt=adjusted(lane,k,bp[lane-1],starts,wins);raw.append(max(q,EPS));tot["ws"]+=wt;tot["wn"]+=1;tot["seen"]+=int(n>0)
            s=sum(raw);cp=[x/s for x in raw];w=wb[rid]
            bll,bbr,bh=score(bp,w);cll,cbr,ch=score(cp,w)
            tot["n"]+=1;tot["bll"]+=bll;tot["bbr"]+=bbr;tot["bh"]+=bh;tot["cll"]+=cll;tot["cbr"]+=cbr;tot["ch"]+=ch
            z=pv[vb[rid]];z["n"]+=1;z["bll"]+=bll;z["bbr"]+=bbr;z["cll"]+=cll;z["cbr"]+=cbr
            day_lw[w]+=1
            for lane in range(1,7):ds[lane][k]+=1
            dw[w][k]+=1
        lw.update(day_lw);gn+=sum(day_lw.values())
        for lane in range(1,7):starts[lane].update(ds[lane]);wins[lane].update(dw[lane])
    n=tot["n"];bll=tot["bll"]/n;bbr=tot["bbr"]/n;cll=tot["cll"]/n;cbr=tot["cbr"]/n
    vdll={};vdbr={};vll=vbr=0
    for v,z in sorted(pv.items()):
        vn=z["n"];dll=z["cll"]/vn-z["bll"]/vn;dbr=z["cbr"]/vn-z["bbr"]/vn;vdll[v]=dll;vdbr[v]=dbr;vll+=dll<0;vbr+=dbr<0
    out={"contract":"V5_B1_PLUS_WIND_WAVE_INCREMENTAL_V1","period":{"start":START,"end":END},
      "candidate":{"baseline":["lane_number"],"added":["wind_speed_m","wave_height_cm"],"snapshot_label":LABEL,"condition_key":"exact stored wind_speed_m x wave_height_cm","estimator":"lane-specific empirical-Bayes shrink to B1","same_day_results_used":False,"parameter_search":False,"v4_logic":False},
      "coverage":{"completed_races":len(races),"scored":n,"coverage_pct":100*n/len(races),"skipped_missing_weather":skip,"invalid_weather_rows":invalid,"seen_condition_lane_pct":100*tot["seen"]/tot["wn"] if tot["wn"] else None,"mean_shrink_weight":tot["ws"]/tot["wn"] if tot["wn"] else None,"venue_count":len(pv)},
      "metrics":{"b1_logloss":bll,"candidate_logloss":cll,"delta_logloss":cll-bll,"b1_brier":bbr,"candidate_brier":cbr,"delta_brier":cbr-bbr,"b1_top1":tot["bh"]/n,"candidate_top1":tot["ch"]/n,"venues_better_logloss":vll,"venues_better_brier":vbr},
      "venue_delta_logloss":vdll,"venue_delta_brier":vdbr,
      "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False,"stake_change":False}}
    print("V5_B1_PLUS_WIND_WAVE_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
