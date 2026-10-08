# -*- coding: utf-8 -*-
"""V5 core incremental: venue lane residual over lane+racer-class baseline."""
from __future__ import annotations
import json,math,os
from collections import Counter,defaultdict
from datetime import date,datetime
from typing import Any
from db_pg import fetch_all

START=os.getenv("START_DATE","2025-07-01")
END=os.getenv("END_DATE","2026-10-05")
EPS=1e-12; ALPHA=1.0

def iso(v:Any)->str:
    if isinstance(v,datetime): return v.date().isoformat()
    if isinstance(v,date): return v.isoformat()
    return str(v)
def cols(t):
    return {str(r["column_name"]) for r in fetch_all(
      "select column_name from information_schema.columns where table_schema='public' and table_name=%s",(t,))}
def winexpr(c):
    if "first_lane" in c:return "rs.first_lane::int"
    return "nullif(substring(regexp_replace(rs.trifecta_ticket::text,'[^0-9]','','g') from 1 for 1),'')::int"
def venueexpr(c):
    if "venue_id" in c and "venue_code" in c:return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
    if "venue_id" in c:return "lpad(r.venue_id::text,2,'0')"
    if "venue_code" in c:return "lpad(r.venue_code::text,2,'0')"
    return "'NA'"
def clean(v):
    if v is None:return None
    s=str(v).strip().upper()
    return s or None
def ii(v):
    try:return int(v)
    except:return -1
def lane_probs(w,n):
    den=n+6*ALPHA
    return [(w[i]+ALPHA)/den for i in range(1,7)]
def score(p,w):
    ll=-math.log(max(p[w-1],EPS));y=[0.0]*6;y[w-1]=1.0
    br=sum((p[i]-y[i])**2 for i in range(6))
    m=max(p);tops=[i+1 for i,x in enumerate(p) if abs(x-m)<1e-15]
    return ll,br,int(len(tops)==1 and tops[0]==w)
def lc_probs(classes,lp,starts,wins):
    raw=[]
    for lane in range(1,7):
        prior=lp[lane-1]; vals=[]; svars=[]
        for cls,n in starts[lane].items():
            if n<=0:continue
            r=(wins[lane][cls]+2*prior)/(n+2)
            vals.append(r);svars.append(max(r*(1-r)/n,EPS))
        tau=0.0
        if len(vals)>=2:
            m=sum(vals)/len(vals)
            tau=max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(svars)/len(svars))
        cls=classes[lane];n=starts[lane][cls];r=(wins[lane][cls]+2*prior)/(n+2)
        wt=0.0 if n<=0 or tau<=0 else tau/(tau+max(r*(1-r)/n,EPS))
        raw.append(max(wt*r+(1-wt)*prior,EPS))
    s=sum(raw);return [x/s for x in raw]
def venue_shrunk(v,gp,vcounts,vn):
    nv=vn[v]
    if nv<=0:return gp[:],[0.0]*6
    active=[x for x,n in vn.items() if n>0]
    if len(active)<2:return gp[:],[0.0]*6
    raw=lane_probs(vcounts[v],nv)
    out=[];weights=[]
    for li in range(6):
        vals=[];svars=[]
        for x in active:
            nx=vn[x]; px=lane_probs(vcounts[x],nx)[li]
            vals.append(px);svars.append(max(px*(1-px)/max(nx,1),EPS))
        m=sum(vals)/len(vals)
        tau=max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(svars)/len(svars)) if len(vals)>1 else 0.0
        pv=raw[li];sv=max(pv*(1-pv)/max(nv,1),EPS)
        wt=tau/(tau+sv) if tau>0 else 0.0
        out.append(max(wt*pv+(1-wt)*gp[li],EPS));weights.append(wt)
    s=sum(out);return [x/s for x in out],weights

def main():
    rc,ec,xc=cols("v2_races"),cols("v2_race_entries"),cols("v2_results")
    if {"lane","racer_class"}-ec:raise RuntimeError("missing entry columns")
    we=winexpr(xc);ve=venueexpr(rc)
    fs=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc:fs.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc:fs.append("coalesce(rs.race_status,'official')='official'")
    races=fetch_all(f"""select r.race_id,r.race_date,{ve} venue,{we} winner
      from v2_races r join v2_results rs on rs.race_id=r.race_id
      where {' and '.join(fs)} order by r.race_date,r.race_id""",(START,END))
    es=fetch_all("""select e.race_id,e.lane,e.racer_class
      from v2_race_entries e join v2_races r on r.race_id=e.race_id
      where r.race_date between %s and %s order by e.race_id,e.lane""",(START,END))

    wb={str(r["race_id"]):int(r["winner"]) for r in races}
    db={str(r["race_id"]):iso(r["race_date"]) for r in races}
    vb={str(r["race_id"]):str(r["venue"]) for r in races}
    by=defaultdict(dict);invalid=0
    for e in es:
        rid=str(e["race_id"])
        if rid not in wb:continue
        lane=ii(e["lane"]);cls=clean(e["racer_class"])
        if lane not in range(1,7) or cls is None:invalid+=1;continue
        by[rid][lane]=cls
    days=defaultdict(list);skip=0
    for rid in wb:
        if len(by[rid])==6 and all(i in by[rid] for i in range(1,7)):days[db[rid]].append(rid)
        else:skip+=1

    lw=Counter();gn=0
    lcs={i:Counter() for i in range(1,7)};lcw={i:Counter() for i in range(1,7)}
    vc=defaultdict(Counter);vn=Counter()
    tot={"n":0,"bll":0.0,"bbr":0.0,"bh":0,"cll":0.0,"cbr":0.0,"ch":0,"ws":0.0,"wn":0}
    pv=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})

    for day in sorted(days):
        gp=lane_probs(lw,gn)
        dlw=Counter();dlcs={i:Counter() for i in range(1,7)};dlcw={i:Counter() for i in range(1,7)}
        dvc=defaultdict(Counter)
        for rid in days[day]:
            classes={lane:by[rid][lane] for lane in range(1,7)}
            bp=lc_probs(classes,gp,lcs,lcw)
            vp,weights=venue_shrunk(vb[rid],gp,vc,vn)
            raw=[max(bp[i]*(vp[i]/max(gp[i],EPS)),EPS) for i in range(6)]
            s=sum(raw);cp=[x/s for x in raw];winner=wb[rid]
            bll,bbr,bh=score(bp,winner);cll,cbr,ch=score(cp,winner)
            tot["n"]+=1;tot["bll"]+=bll;tot["bbr"]+=bbr;tot["bh"]+=bh
            tot["cll"]+=cll;tot["cbr"]+=cbr;tot["ch"]+=ch;tot["ws"]+=sum(weights);tot["wn"]+=len(weights)
            z=pv[vb[rid]];z["n"]+=1;z["bll"]+=bll;z["bbr"]+=bbr;z["cll"]+=cll;z["cbr"]+=cbr
            dlw[winner]+=1;dvc[vb[rid]][winner]+=1
            for lane in range(1,7):dlcs[lane][classes[lane]]+=1
            dlcw[winner][classes[winner]]+=1
        lw.update(dlw);gn+=sum(dlw.values())
        for lane in range(1,7):lcs[lane].update(dlcs[lane]);lcw[lane].update(dlcw[lane])
        for v,c in dvc.items():vc[v].update(c);vn[v]+=sum(c.values())

    n=tot["n"]
    if not n:raise RuntimeError("zero scoreable races")
    bll=tot["bll"]/n;bbr=tot["bbr"]/n;cll=tot["cll"]/n;cbr=tot["cbr"]/n
    vll=vbr=0;vdll={};vdbr={}
    for v,z in sorted(pv.items()):
        vn0=z["n"];dll=z["cll"]/vn0-z["bll"]/vn0;dbr=z["cbr"]/vn0-z["bbr"]/vn0
        vdll[v]=dll;vdbr[v]=dbr;vll+=dll<0;vbr+=dbr<0
    out={"contract":"V5_LANE_CLASS_PLUS_VENUE_RESIDUAL_V1","period":{"start":START,"end":END},
      "candidate":{"baseline":["lane_number","racer_class"],"added":["venue_lane_residual"],"residual":"shrunk venue lane probability / global lane probability","same_day_results_used":False,"parameter_search":False,"v4_logic":False},
      "coverage":{"completed_races":len(races),"scored":n,"coverage_pct":100*n/len(races),"skipped":skip,"invalid_entry_rows":invalid,"venue_count":len(pv),"mean_lane_shrink_weight":tot["ws"]/tot["wn"] if tot["wn"] else 0.0},
      "metrics":{"baseline_logloss":bll,"candidate_logloss":cll,"delta_logloss":cll-bll,"baseline_brier":bbr,"candidate_brier":cbr,"delta_brier":cbr-bbr,"baseline_top1":tot["bh"]/n,"candidate_top1":tot["ch"]/n,"venues_better_logloss":vll,"venues_better_brier":vbr},
      "venue_delta_logloss":vdll,"venue_delta_brier":vdbr,
      "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False,"stake_change":False}}
    print("V5_LANE_CLASS_PLUS_VENUE_RESIDUAL_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
