# -*- coding: utf-8 -*-
"""V5 B14G: wind direction incremental over B1+venue EB baseline."""
from __future__ import annotations
import json, math, os
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any
from db_pg import fetch_all

START=os.getenv("START_DATE","2025-07-01")
END=os.getenv("END_DATE","2026-10-05")
LABEL="historical"; ALPHA=1.0; EPS=1e-12

def iso(v:Any)->str:
    if isinstance(v,datetime): return v.date().isoformat()
    if isinstance(v,date): return v.isoformat()
    return str(v)

def cols(t):
    return {str(r["column_name"]) for r in fetch_all(
        "select column_name from information_schema.columns where table_schema='public' and table_name=%s",(t,))}

def winexpr(c):
    if "first_lane" in c: return "rs.first_lane::int"
    return "nullif(substring(regexp_replace(rs.trifecta_ticket::text,'[^0-9]','','g') from 1 for 1),'')::int"

def venueexpr(c):
    if "venue_id" in c and "venue_code" in c:
        return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
    return "lpad(r."+("venue_id" if "venue_id" in c else "venue_code")+"::text,2,'0')"

def probs(c,n):
    d=n+6*ALPHA
    return [(c.get(i,0)+ALPHA)/d for i in range(1,7)]

def score(p,w):
    ll=-math.log(max(p[w-1],EPS)); y=[0.0]*6; y[w-1]=1.0
    br=sum((p[i]-y[i])**2 for i in range(6))
    m=max(p); tops=[i+1 for i,x in enumerate(p) if abs(x-m)<1e-15]
    return ll,br,int(len(tops)==1 and tops[0]==w)

def venue_baseline(v,gp,vc,vn):
    nv=vn.get(v,0)
    if nv<=0: return gp[:],[0.0]*6
    active=[x for x,n in vn.items() if n>0]
    if len(active)<2: return gp[:],[0.0]*6
    raw=probs(vc[v],nv); out=[]; ws=[]
    for li in range(6):
        vals=[]; svars=[]
        for vv in active:
            n=vn[vv]; pv=probs(vc[vv],n)[li]
            vals.append(pv); svars.append(max(pv*(1-pv)/max(n,1),EPS))
        mean=sum(vals)/len(vals)
        sv=sum((x-mean)**2 for x in vals)/(len(vals)-1) if len(vals)>1 else 0.0
        tau=max(0.0,sv-sum(svars)/len(svars))
        pv=raw[li]; s2=max(pv*(1-pv)/max(nv,1),EPS)
        wt=tau/(tau+s2) if tau>0 else 0.0
        out.append(max(wt*pv+(1-wt)*gp[li],EPS)); ws.append(wt)
    s=sum(out); return [x/s for x in out],ws

def direction_candidate(v,d,vp,dc,dn):
    key=(v,d); n=dn.get(key,0)
    if n<=0: return vp[:],[0.0]*6
    dirs=[dd for (vv,dd),nn in dn.items() if vv==v and nn>0]
    if len(dirs)<2: return vp[:],[0.0]*6
    raw=probs(dc[key],n); out=[]; ws=[]
    for li in range(6):
        vals=[]; svars=[]
        for dd in dirs:
            kk=(v,dd); nn=dn[kk]; pd=probs(dc[kk],nn)[li]
            vals.append(pd); svars.append(max(pd*(1-pd)/max(nn,1),EPS))
        mean=sum(vals)/len(vals)
        sv=sum((x-mean)**2 for x in vals)/(len(vals)-1) if len(vals)>1 else 0.0
        tau=max(0.0,sv-sum(svars)/len(svars))
        pd=raw[li]; s2=max(pd*(1-pd)/max(n,1),EPS)
        wt=tau/(tau+s2) if tau>0 else 0.0
        out.append(max(wt*pd+(1-wt)*vp[li],EPS)); ws.append(wt)
    s=sum(out); return [x/s for x in out],ws

def main():
    rc,xc,wc=cols("v2_races"),cols("v2_results"),cols("v2_realtime_weather_snapshots")
    if "wind_direction" not in wc: raise RuntimeError("wind_direction unavailable")
    we=winexpr(xc); ve=venueexpr(rc)
    fs=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc: fs.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc: fs.append("coalesce(rs.race_status,'official')='official'")
    races=fetch_all(f"""select r.race_id,r.race_date,{ve} venue,{we} winner
      from v2_races r join v2_results rs on rs.race_id=r.race_id
      where {' and '.join(fs)} order by r.race_date,r.race_id""",(START,END))
    wr=fetch_all("""select w.race_id,w.wind_direction
      from v2_realtime_weather_snapshots w join v2_races r on r.race_id=w.race_id
      where r.race_date between %s and %s and w.snapshot_label=%s
      order by r.race_date,w.race_id,w.snapshot_at""",(START,END,LABEL))
    direction={}
    invalid=0
    for x in wr:
        s=str(x.get("wind_direction") or "").strip()
        if not s: invalid+=1; continue
        direction[str(x["race_id"])]=s

    byday=defaultdict(list); missing=0
    for r in races:
        rid=str(r["race_id"])
        if rid not in direction: missing+=1; continue
        byday[iso(r["race_date"])].append(r)

    gc=Counter(); gn=0
    vc=defaultdict(Counter); vn=Counter()
    dc=defaultdict(Counter); dn=Counter()
    tot={"n":0,"bll":0.0,"bbr":0.0,"bh":0,"cll":0.0,"cbr":0.0,"ch":0,
         "vws":0.0,"vwn":0,"dws":0.0,"dwn":0,"seen":0}
    pv=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})
    dir_dist=Counter()

    for day in sorted(byday):
        gp=probs(gc,gn)
        dgc=Counter(); dvc=defaultdict(Counter); ddc=defaultdict(Counter)
        for r in byday[day]:
            rid=str(r["race_id"]); v=str(r["venue"]); d=direction[rid]; w=int(r["winner"])
            vp,vw=venue_baseline(v,gp,vc,vn)
            cp,dw=direction_candidate(v,d,vp,dc,dn)
            bll,bbr,bh=score(vp,w); cll,cbr,ch=score(cp,w)
            tot["n"]+=1;tot["bll"]+=bll;tot["bbr"]+=bbr;tot["bh"]+=bh
            tot["cll"]+=cll;tot["cbr"]+=cbr;tot["ch"]+=ch
            tot["vws"]+=sum(vw);tot["vwn"]+=len(vw);tot["dws"]+=sum(dw);tot["dwn"]+=len(dw)
            tot["seen"]+=int(dn.get((v,d),0)>0);dir_dist[d]+=1
            z=pv[v];z["n"]+=1;z["bll"]+=bll;z["bbr"]+=bbr;z["cll"]+=cll;z["cbr"]+=cbr
            dgc[w]+=1; dvc[v][w]+=1; ddc[(v,d)][w]+=1
        gc.update(dgc); gn+=sum(dgc.values())
        for v,c in dvc.items(): vc[v].update(c); vn[v]+=sum(c.values())
        for k,c in ddc.items(): dc[k].update(c); dn[k]+=sum(c.values())

    n=tot["n"]
    if not n: raise RuntimeError("zero scoreable races")
    bll=tot["bll"]/n;bbr=tot["bbr"]/n;cll=tot["cll"]/n;cbr=tot["cbr"]/n
    vll=vbr=0; vdll={};vdbr={}
    for v,z in sorted(pv.items()):
        vn0=z["n"]; dll=z["cll"]/vn0-z["bll"]/vn0; dbr=z["cbr"]/vn0-z["bbr"]/vn0
        vdll[v]=dll;vdbr[v]=dbr;vll+=dll<0;vbr+=dbr<0
    out={"contract":"V5_B1_VENUE_PLUS_WIND_DIRECTION_INCREMENTAL_V1",
      "period":{"start":START,"end":END},
      "candidate":{"baseline":"B1 lane + venue empirical-Bayes shrinkage","added":"wind_direction within venue","snapshot_label":LABEL,"exact_stored_category":True,"same_day_results_used":False,"parameter_search":False,"v4_logic":False},
      "coverage":{"completed_races":len(races),"scored":n,"coverage_pct":100*n/len(races),"missing_direction_races":missing,"invalid_weather_rows":invalid,"seen_venue_direction_pct":100*tot["seen"]/n,"distinct_directions":len(dir_dist),"direction_distribution":dict(sorted(dir_dist.items())),"venue_count":len(pv)},
      "metrics":{"baseline_logloss":bll,"candidate_logloss":cll,"delta_logloss":cll-bll,"baseline_brier":bbr,"candidate_brier":cbr,"delta_brier":cbr-bbr,"baseline_top1":tot["bh"]/n,"candidate_top1":tot["ch"]/n,"venues_better_logloss":vll,"venues_better_brier":vbr,"mean_venue_shrink_weight":tot["vws"]/tot["vwn"] if tot["vwn"] else 0.0,"mean_direction_shrink_weight":tot["dws"]/tot["dwn"] if tot["dwn"] else 0.0},
      "venue_delta_logloss":vdll,"venue_delta_brier":vdbr,
      "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False,"stake_change":False}}
    print("V5_B1_VENUE_PLUS_WIND_DIRECTION_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=="__main__": main()
