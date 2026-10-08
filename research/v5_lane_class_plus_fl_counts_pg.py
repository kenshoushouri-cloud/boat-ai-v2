# -*- coding: utf-8 -*-
"""V5 B13A: F/L counts incremental over lane+racer-class baseline."""
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
    if isinstance(v,datetime):return v.date().isoformat()
    if isinstance(v,date):return v.isoformat()
    return str(v)
def cols(t):
    return {str(r["column_name"]) for r in fetch_all(
        "select column_name from information_schema.columns where table_schema='public' and table_name=%s",(t,))}
def winexpr(c):
    if "first_lane" in c:return "rs.first_lane::int"
    return "nullif(substring(regexp_replace(rs.trifecta_ticket::text,'[^0-9]','','g') from 1 for 1),'')::int"
def venueexpr(c):
    if "venue_id" in c and "venue_code" in c:
        return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
    return "lpad(r."+("venue_id" if "venue_id" in c else "venue_code")+"::text,2,'0')"
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

def cell(key,starts,wins,prior):
    n=starts[key];w=wins[key]
    return (w+2*prior)/(n+2),n
def tau(prefix,prior,starts,wins):
    vals=[];svars=[]
    for key,n in starts.items():
        if n<=0 or key[:2]!=prefix:continue
        r,_=cell(key,starts,wins,prior);vals.append(r);svars.append(max(r*(1-r)/n,EPS))
    if len(vals)<2:return 0.0
    m=sum(vals)/len(vals)
    return max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(svars)/len(svars))
def adjusted(key,prior,starts,wins):
    t=tau(key[:2],prior,starts,wins);r,n=cell(key,starts,wins,prior)
    if n<=0 or t<=0:return prior,n,0.0
    sv=max(r*(1-r)/n,EPS);wt=t/(t+sv)
    return wt*r+(1-wt)*prior,n,wt

def lc_cell(lane,cls,starts,wins,prior):
    n=starts[lane][cls];w=wins[lane][cls]
    return (w+2*prior)/(n+2),n
def lc_probs(classes,lp,starts,wins):
    raw=[]
    for lane in range(1,7):
        prior=lp[lane-1];vals=[];svars=[]
        for cls,n in starts[lane].items():
            if n<=0:continue
            r,_=lc_cell(lane,cls,starts,wins,prior);vals.append(r);svars.append(max(r*(1-r)/n,EPS))
        t=0.0
        if len(vals)>=2:
            m=sum(vals)/len(vals);t=max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(svars)/len(svars))
        r,n=lc_cell(lane,classes[lane],starts,wins,prior)
        if n<=0 or t<=0:wt=0.0
        else:
            sv=max(r*(1-r)/n,EPS);wt=t/(t+sv)
        raw.append(max(wt*r+(1-wt)*prior,EPS))
    s=sum(raw);return [x/s for x in raw]

def main():
    rc,ec,xc=cols("v2_races"),cols("v2_race_entries"),cols("v2_results")
    need={"racer_class","f_count","l_count","lane"}
    if need-ec:raise RuntimeError("missing entry columns: "+str(sorted(need-ec)))
    we=winexpr(xc);ve=venueexpr(rc)
    fs=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc:fs.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc:fs.append("coalesce(rs.race_status,'official')='official'")
    races=fetch_all(f"select r.race_id,r.race_date,{ve} venue,{we} winner from v2_races r join v2_results rs on rs.race_id=r.race_id where {' and '.join(fs)} order by r.race_date,r.race_id",(START,END))
    es=fetch_all("""select e.race_id,e.lane,e.racer_class,e.f_count,e.l_count
      from v2_race_entries e join v2_races r on r.race_id=e.race_id
      where r.race_date between %s and %s order by e.race_id,e.lane""",(START,END))
    wb={str(r["race_id"]):int(r["winner"]) for r in races};db={str(r["race_id"]):iso(r["race_date"]) for r in races};vb={str(r["race_id"]):str(r["venue"]) for r in races}
    by=defaultdict(dict);invalid=0
    for e in es:
        rid=str(e["race_id"])
        if rid not in wb:continue
        lane=ii(e["lane"]);cls=clean(e["racer_class"]);f=ii(e["f_count"]);l=ii(e["l_count"])
        if lane not in range(1,7) or cls is None or f<0 or l<0:invalid+=1;continue
        by[rid][lane]=(cls,f,l)
    days=defaultdict(list);skip=0
    for rid in wb:
        if len(by[rid])==6 and all(i in by[rid] for i in range(1,7)):days[db[rid]].append(rid)
        else:skip+=1

    lw=Counter();gn=0;lc_s={i:Counter() for i in range(1,7)};lc_w={i:Counter() for i in range(1,7)}
    fl_s=Counter();fl_w=Counter()
    tot={"n":0,"bll":0.0,"bbr":0.0,"bh":0,"cll":0.0,"cbr":0.0,"ch":0,"seen":0,"obs":0,"ws":0.0}
    pv=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})
    dist=Counter()

    for day in sorted(days):
        lp=lane_probs(lw,gn)
        dlw=Counter();dlcs={i:Counter() for i in range(1,7)};dlcw={i:Counter() for i in range(1,7)}
        dfs=Counter();dfw=Counter()
        for rid in days[day]:
            classes={lane:by[rid][lane][0] for lane in range(1,7)}
            bp=lc_probs(classes,lp,lc_s,lc_w)
            raw=[]
            for lane in range(1,7):
                cls,f,l=by[rid][lane];key=(lane,cls,f,l);dist[(f,l)]+=1
                q,n,wt=adjusted(key,bp[lane-1],fl_s,fl_w)
                raw.append(max(q,EPS));tot["seen"]+=int(n>0);tot["obs"]+=1;tot["ws"]+=wt
            s=sum(raw);cp=[x/s for x in raw];winner=wb[rid]
            bll,bbr,bh=score(bp,winner);cll,cbr,ch=score(cp,winner)
            tot["n"]+=1;tot["bll"]+=bll;tot["bbr"]+=bbr;tot["bh"]+=bh;tot["cll"]+=cll;tot["cbr"]+=cbr;tot["ch"]+=ch
            z=pv[vb[rid]];z["n"]+=1;z["bll"]+=bll;z["bbr"]+=bbr;z["cll"]+=cll;z["cbr"]+=cbr
            dlw[winner]+=1
            for lane in range(1,7):
                cls,f,l=by[rid][lane];dlcs[lane][cls]+=1;dfs[(lane,cls,f,l)]+=1
            wcls,wf,wl=by[rid][winner];dlcw[winner][wcls]+=1;dfw[(winner,wcls,wf,wl)]+=1
        lw.update(dlw);gn+=sum(dlw.values())
        for lane in range(1,7):lc_s[lane].update(dlcs[lane]);lc_w[lane].update(dlcw[lane])
        fl_s.update(dfs);fl_w.update(dfw)

    n=tot["n"];bll=tot["bll"]/n;bbr=tot["bbr"]/n;cll=tot["cll"]/n;cbr=tot["cbr"]/n
    vdll={};vdbr={};vll=vbr=0
    for v,z in sorted(pv.items()):
        vn=z["n"];dll=z["cll"]/vn-z["bll"]/vn;dbr=z["cbr"]/vn-z["bbr"]/vn
        vdll[v]=dll;vdbr[v]=dbr;vll+=dll<0;vbr+=dbr<0
    out={"contract":"V5_LANE_CLASS_PLUS_FL_COUNTS_V1","period":{"start":START,"end":END},
      "candidate":{"baseline":["lane_number","racer_class"],"added":["f_count","l_count"],"key":"lane x class x exact f_count x l_count","estimator":"empirical-Bayes shrink to lane+class baseline","same_day_results_used":False,"parameter_search":False,"v4_logic":False},
      "coverage":{"completed_races":len(races),"scored":n,"coverage_pct":100*n/len(races),"skipped":skip,"invalid_entry_rows":invalid,"seen_cell_pct":100*tot["seen"]/tot["obs"] if tot["obs"] else None,"mean_shrink_weight":tot["ws"]/tot["obs"] if tot["obs"] else None,"fl_distribution":{f"F{k[0]}L{k[1]}":v for k,v in sorted(dist.items())},"venue_count":len(pv)},
      "metrics":{"baseline_logloss":bll,"candidate_logloss":cll,"delta_logloss":cll-bll,"baseline_brier":bbr,"candidate_brier":cbr,"delta_brier":cbr-bbr,"baseline_top1":tot["bh"]/n,"candidate_top1":tot["ch"]/n,"venues_better_logloss":vll,"venues_better_brier":vbr},
      "venue_delta_logloss":vdll,"venue_delta_brier":vdbr,
      "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False,"stake_change":False}}
    print("V5_LANE_CLASS_PLUS_FL_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
