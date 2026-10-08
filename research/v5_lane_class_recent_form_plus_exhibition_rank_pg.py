# -*- coding: utf-8 -*-
"""V5 core redundancy: add exhibition-time-rank residual over lane+class+recent-form."""
from __future__ import annotations
import json,math,os
from collections import Counter,defaultdict
from datetime import date,datetime
from typing import Any
from db_pg import fetch_all

START=os.getenv("START_DATE","2025-07-01")
END=os.getenv("END_DATE","2026-10-05")
LABEL="historical"
EPS=1e-12; ALPHA=1.0; MIN_VALID=3; MAX_HISTORY=5; NEUTRAL=0.5

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
def rankkey(v):
    try:x=int(v)
    except:return None
    return str(x) if 1<=x<=6 else None
def parse_form(v):
    if v is None:return []
    x=v
    if isinstance(v,str):
        try:x=json.loads(v)
        except:return []
    if isinstance(x,dict):x=x.get("history") or x.get("recent_form") or []
    if not isinstance(x,list):return []
    return [dict(z) for z in x[:MAX_HISTORY] if isinstance(z,dict)]
def recent_strength(v):
    valid=[]
    for item in parse_form(v):
        try:f=int(item.get("finish_position"))
        except:continue
        if 1<=f<=6:valid.append(f)
    if len(valid)<MIN_VALID:return NEUTRAL,len(valid)
    top3=sum(1 for f in valid if f<=3)
    return (top3+1.0)/(len(valid)+2.0),len(valid)
def lane_probs(w,n):
    d=n+6*ALPHA
    return [(w[i]+ALPHA)/d for i in range(1,7)]
def score(p,w):
    ll=-math.log(max(p[w-1],EPS));y=[0.0]*6;y[w-1]=1.0
    br=sum((p[i]-y[i])**2 for i in range(6))
    m=max(p);tops=[i+1 for i,x in enumerate(p) if abs(x-m)<1e-15]
    return ll,br,int(len(tops)==1 and tops[0]==w)
def lc_probs(classes,lp,starts,wins):
    raw=[]
    for lane in range(1,7):
        prior=lp[lane-1];vals=[];svars=[]
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
def rank_adjusted(key,prior,starts,wins):
    prefix=key[:2];vals=[];svars=[]
    for k,n in starts.items():
        if n<=0 or k[:2]!=prefix:continue
        r=(wins[k]+2*prior)/(n+2)
        vals.append(r);svars.append(max(r*(1-r)/n,EPS))
    tau=0.0
    if len(vals)>=2:
        m=sum(vals)/len(vals)
        tau=max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(svars)/len(svars))
    n=starts[key];r=(wins[key]+2*prior)/(n+2)
    if n<=0 or tau<=0:return prior,n,0.0
    wt=tau/(tau+max(r*(1-r)/n,EPS))
    return wt*r+(1-wt)*prior,n,wt

def main():
    rc,ec,xc,cc=cols("v2_races"),cols("v2_race_entries"),cols("v2_results"),cols("v2_realtime_exhibition_snapshots")
    if {"lane","racer_class","recent_form"}-ec:raise RuntimeError("missing entry columns")
    if {"race_id","lane","exhibition_time_rank"}-cc:raise RuntimeError("missing exhibition columns")
    we=winexpr(xc);ve=venueexpr(rc)
    fs=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc:fs.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc:fs.append("coalesce(rs.race_status,'official')='official'")
    races=fetch_all(f"""select r.race_id,r.race_date,{ve} venue,{we} winner
      from v2_races r join v2_results rs on rs.race_id=r.race_id
      where {' and '.join(fs)} order by r.race_date,r.race_id""",(START,END))
    es=fetch_all("""select e.race_id,e.lane,e.racer_class,e.recent_form,x.exhibition_time_rank
      from v2_race_entries e
      join v2_races r on r.race_id=e.race_id
      left join v2_realtime_exhibition_snapshots x
        on x.race_id=e.race_id and x.lane=e.lane and x.snapshot_label=%s
      where r.race_date between %s and %s order by e.race_id,e.lane""",(LABEL,START,END))

    wb={str(r["race_id"]):int(r["winner"]) for r in races}
    db={str(r["race_id"]):iso(r["race_date"]) for r in races}
    vb={str(r["race_id"]):str(r["venue"]) for r in races}
    by=defaultdict(dict);invalid=0
    for e in es:
        rid=str(e["race_id"])
        if rid not in wb:continue
        lane=ii(e["lane"]);cls=clean(e["racer_class"]);rk=rankkey(e["exhibition_time_rank"])
        rs,nvalid=recent_strength(e["recent_form"])
        if lane not in range(1,7) or cls is None or rk is None:
            invalid+=1;continue
        by[rid][lane]=(cls,rs,nvalid,rk)

    days=defaultdict(list);skip=0
    for rid in wb:
        if len(by[rid])==6 and all(i in by[rid] for i in range(1,7)):days[db[rid]].append(rid)
        else:skip+=1

    lw=Counter();gn=0
    lcs={i:Counter() for i in range(1,7)};lcw={i:Counter() for i in range(1,7)}
    rks=Counter();rkw=Counter()
    tot={"n":0,"bll":0.0,"bbr":0.0,"bh":0,"cll":0.0,"cbr":0.0,"ch":0,"seen":0,"obs":0,"ws":0.0,"eligible":0}
    pv=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})

    for day in sorted(days):
        lp=lane_probs(lw,gn)
        dlw=Counter();dlcs={i:Counter() for i in range(1,7)};dlcw={i:Counter() for i in range(1,7)}
        drks=Counter();drkw=Counter()
        for rid in days[day]:
            classes={lane:by[rid][lane][0] for lane in range(1,7)}
            lcp=lc_probs(classes,lp,lcs,lcw)

            rfraw=[]
            for lane in range(1,7):
                _,rs,nvalid,_=by[rid][lane]
                rfraw.append(max(lcp[lane-1]*(rs/NEUTRAL),EPS))
                tot["eligible"]+=int(nvalid>=MIN_VALID)
            s=sum(rfraw);bp=[x/s for x in rfraw]

            craw=[]
            for lane in range(1,7):
                cls,_,_,rk=by[rid][lane];key=(lane,cls,rk)
                q,n,wt=rank_adjusted(key,lcp[lane-1],rks,rkw)
                residual=q/max(lcp[lane-1],EPS)
                craw.append(max(bp[lane-1]*residual,EPS))
                tot["seen"]+=int(n>0);tot["obs"]+=1;tot["ws"]+=wt
            s=sum(craw);cp=[x/s for x in craw];winner=wb[rid]

            bll,bbr,bh=score(bp,winner);cll,cbr,ch=score(cp,winner)
            tot["n"]+=1;tot["bll"]+=bll;tot["bbr"]+=bbr;tot["bh"]+=bh
            tot["cll"]+=cll;tot["cbr"]+=cbr;tot["ch"]+=ch
            z=pv[vb[rid]];z["n"]+=1;z["bll"]+=bll;z["bbr"]+=bbr;z["cll"]+=cll;z["cbr"]+=cbr

            dlw[winner]+=1
            for lane in range(1,7):
                cls,_,_,rk=by[rid][lane]
                dlcs[lane][cls]+=1;drks[(lane,cls,rk)]+=1
            wcls,_,_,wrk=by[rid][winner]
            dlcw[winner][wcls]+=1;drkw[(winner,wcls,wrk)]+=1

        lw.update(dlw);gn+=sum(dlw.values())
        for lane in range(1,7):lcs[lane].update(dlcs[lane]);lcw[lane].update(dlcw[lane])
        rks.update(drks);rkw.update(drkw)

    n=tot["n"]
    if not n:raise RuntimeError("zero scoreable races")
    bll=tot["bll"]/n;bbr=tot["bbr"]/n;cll=tot["cll"]/n;cbr=tot["cbr"]/n
    vll=vbr=0;vdll={};vdbr={}
    for v,z in sorted(pv.items()):
        vn=z["n"];dll=z["cll"]/vn-z["bll"]/vn;dbr=z["cbr"]/vn-z["bbr"]/vn
        vdll[v]=dll;vdbr[v]=dbr;vll+=dll<0;vbr+=dbr<0

    out={"contract":"V5_LANE_CLASS_RECENT_FORM_PLUS_EXHIBITION_RANK_V1","period":{"start":START,"end":END},
      "candidate":{"baseline":["lane_number","racer_class","recent_form_last5_top3"],"added":["exhibition_time_rank_residual"],"historical_policy":"docs/V5_EXHIBITION_DATA_POLICY_20261008.md","same_day_results_used":False,"parameter_search":False,"v4_logic":False},
      "coverage":{"completed_races":len(races),"scored":n,"coverage_pct":100*n/len(races),"skipped":skip,"invalid_or_missing_rows":invalid,"feature_eligible_recent_form_lane_pct":100*tot["eligible"]/(n*6),"rank_seen_cell_pct":100*tot["seen"]/tot["obs"] if tot["obs"] else None,"rank_mean_shrink_weight":tot["ws"]/tot["obs"] if tot["obs"] else None,"venue_count":len(pv)},
      "metrics":{"baseline_logloss":bll,"candidate_logloss":cll,"delta_logloss":cll-bll,"baseline_brier":bbr,"candidate_brier":cbr,"delta_brier":cbr-bbr,"baseline_top1":tot["bh"]/n,"candidate_top1":tot["ch"]/n,"venues_better_logloss":vll,"venues_better_brier":vbr},
      "venue_delta_logloss":vdll,"venue_delta_brier":vdbr,
      "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False,"stake_change":False}}
    print("V5_LC_RF_PLUS_EXHIBITION_RANK_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
