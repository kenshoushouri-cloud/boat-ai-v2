# -*- coding: utf-8 -*-
"""V5 B8A: opponent composition incremental over lane+racer-class baseline."""
from __future__ import annotations
import json,math,os
from collections import Counter,defaultdict
from datetime import date,datetime
from typing import Any
from db_pg import fetch_all

START=os.getenv("START_DATE","2025-07-01")
END=os.getenv("END_DATE","2026-10-05")
EPS=1e-12
ALPHA=1.0

def iso(v:Any)->str:
    if isinstance(v,datetime): return v.date().isoformat()
    if isinstance(v,date): return v.isoformat()
    return str(v)
def cols(t:str)->set[str]:
    return {str(r["column_name"]) for r in fetch_all(
        "select column_name from information_schema.columns where table_schema='public' and table_name=%s",(t,))}
def winner_expr(c:set[str])->str:
    if "first_lane" in c:return "rs.first_lane::int"
    return "nullif(substring(regexp_replace(rs.trifecta_ticket::text,'[^0-9]','','g') from 1 for 1),'')::int"
def venue_expr(c:set[str])->str:
    if "venue_id" in c and "venue_code" in c:
        return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
    if "venue_id" in c:return "lpad(r.venue_id::text,2,'0')"
    return "lpad(r.venue_code::text,2,'0')"
def clean(v:Any)->str|None:
    if v is None:return None
    s=str(v).strip().upper()
    return s or None
def lane_probs(w:Counter[int],n:int)->list[float]:
    den=n+6*ALPHA
    return [(w[i]+ALPHA)/den for i in range(1,7)]
def score(p:list[float],w:int)->tuple[float,float,int]:
    ll=-math.log(max(p[w-1],EPS)); y=[0.0]*6;y[w-1]=1.0
    br=sum((p[i]-y[i])**2 for i in range(6))
    m=max(p); tops=[i+1 for i,x in enumerate(p) if abs(x-m)<1e-15]
    return ll,br,int(len(tops)==1 and tops[0]==w)

def lc_rate(lane:int,cls:str,starts,wins,prior:float)->tuple[float,int]:
    n=starts[lane][cls]; w=wins[lane][cls]
    return (w+2*prior)/(n+2),n

def lane_class_probs(classes,lp,starts,wins):
    raw=[]; meta={}
    for lane in range(1,7):
        prior=lp[lane-1]
        vals=[]; svars=[]
        for c,n in starts[lane].items():
            if n<=0:continue
            r,_=lc_rate(lane,c,starts,wins,prior)
            vals.append(r); svars.append(max(r*(1-r)/n,EPS))
        tau2=0.0
        if len(vals)>=2:
            m=sum(vals)/len(vals)
            tau2=max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(svars)/len(svars))
        r,n=lc_rate(lane,classes[lane],starts,wins,prior)
        if n<=0 or tau2<=0:wgt=0.0
        else:
            svar=max(r*(1-r)/n,EPS); wgt=tau2/(tau2+svar)
        q=max(wgt*r+(1-wgt)*prior,EPS)
        raw.append(q);meta[(lane,classes[lane])]={"base":q}
    s=sum(raw)
    return [x/s for x in raw],meta

def pair_rate(key,base,pstarts,pwins):
    n=pstarts[key]; w=pwins[key]
    return (w+2*base)/(n+2),n

def pair_tau(own_lane,own_cls,base,pstarts,pwins):
    vals=[];svars=[]
    prefix=(own_lane,own_cls)
    for key,n in pstarts.items():
        if n<=0 or key[:2]!=prefix:continue
        r,_=pair_rate(key,base,pstarts,pwins)
        vals.append(r);svars.append(max(r*(1-r)/n,EPS))
    if len(vals)<2:return 0.0
    m=sum(vals)/len(vals)
    return max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(svars)/len(svars))

def candidate_probs(classes,base_probs,pstarts,pwins):
    raw=[];matched=0;weights=[]
    for lane in range(1,7):
        base=max(base_probs[lane-1],EPS)
        tau2=pair_tau(lane,classes[lane],base,pstarts,pwins)
        logs=[]
        for opp_lane in range(1,7):
            if opp_lane==lane:continue
            key=(lane,classes[lane],opp_lane,classes[opp_lane])
            r,n=pair_rate(key,base,pstarts,pwins)
            if n<=0 or tau2<=0:wgt=0.0
            else:
                svar=max(r*(1-r)/n,EPS); wgt=tau2/(tau2+svar)
            q=max(wgt*r+(1-wgt)*base,EPS)
            logs.append(math.log(q/base))
            matched+=int(n>0);weights.append(wgt)
        factor=math.exp(sum(logs)/len(logs)) if logs else 1.0
        raw.append(base*factor)
    s=sum(raw)
    return [x/s for x in raw],matched,weights

def main():
    rc,ec,xc=cols("v2_races"),cols("v2_race_entries"),cols("v2_results")
    if "racer_class" not in ec:raise RuntimeError("racer_class unavailable")
    we=winner_expr(xc);ve=venue_expr(rc)
    fs=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc:fs.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc:fs.append("coalesce(rs.race_status,'official')='official'")
    races=fetch_all(f"select r.race_id,r.race_date,{ve} venue,{we} winner from v2_races r join v2_results rs on rs.race_id=r.race_id where {' and '.join(fs)} order by r.race_date,r.race_id",(START,END))
    entries=fetch_all("select e.race_id,e.lane,e.racer_class from v2_race_entries e join v2_races r on r.race_id=e.race_id where r.race_date between %s and %s order by e.race_id,e.lane",(START,END))

    wb={str(r["race_id"]):int(r["winner"]) for r in races}
    db={str(r["race_id"]):iso(r["race_date"]) for r in races}
    vb={str(r["race_id"]):str(r["venue"]) for r in races}
    cb=defaultdict(dict);invalid=0
    for e in entries:
        rid=str(e["race_id"])
        if rid not in wb:continue
        try:lane=int(e["lane"])
        except:invalid+=1;continue
        cls=clean(e.get("racer_class"))
        if lane not in range(1,7) or cls is None:invalid+=1;continue
        cb[rid][lane]=cls
    days=defaultdict(list);skip=0
    for rid in wb:
        if len(cb[rid])==6 and all(i in cb[rid] for i in range(1,7)):days[db[rid]].append(rid)
        else:skip+=1

    lw=Counter();gn=0
    lc_st={i:Counter() for i in range(1,7)};lc_w={i:Counter() for i in range(1,7)}
    ps=Counter();pw=Counter()
    tot={"n":0,"bll":0.0,"bbr":0.0,"bh":0,"cll":0.0,"cbr":0.0,"ch":0,"matched":0,"pairs":0,"ws":0.0,"wn":0}
    pv=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})

    for ds in sorted(days):
        lp=lane_probs(lw,gn)
        day_lw=Counter();day_lcs={i:Counter() for i in range(1,7)};day_lcw={i:Counter() for i in range(1,7)}
        day_ps=Counter();day_pw=Counter()
        for rid in days[ds]:
            classes=cb[rid];winner=wb[rid]
            bp,_=lane_class_probs(classes,lp,lc_st,lc_w)
            cp,matched,weights=candidate_probs(classes,bp,ps,pw)
            bll,bbr,bh=score(bp,winner);cll,cbr,ch=score(cp,winner)
            tot["n"]+=1;tot["bll"]+=bll;tot["bbr"]+=bbr;tot["bh"]+=bh;tot["cll"]+=cll;tot["cbr"]+=cbr;tot["ch"]+=ch
            tot["matched"]+=matched;tot["pairs"]+=30;tot["ws"]+=sum(weights);tot["wn"]+=len(weights)
            z=pv[vb[rid]];z["n"]+=1;z["bll"]+=bll;z["bbr"]+=bbr;z["cll"]+=cll;z["cbr"]+=cbr

            day_lw[winner]+=1
            for lane in range(1,7):day_lcs[lane][classes[lane]]+=1
            day_lcw[winner][classes[winner]]+=1
            for lane in range(1,7):
                for opp in range(1,7):
                    if opp==lane:continue
                    key=(lane,classes[lane],opp,classes[opp]);day_ps[key]+=1
                    if lane==winner:day_pw[key]+=1

        lw.update(day_lw);gn+=sum(day_lw.values())
        for lane in range(1,7):
            lc_st[lane].update(day_lcs[lane]);lc_w[lane].update(day_lcw[lane])
        ps.update(day_ps);pw.update(day_pw)

    n=tot["n"];bll=tot["bll"]/n;bbr=tot["bbr"]/n;cll=tot["cll"]/n;cbr=tot["cbr"]/n
    vdll={};vdbr={};vll=vbr=0
    for v,z in sorted(pv.items()):
        vn=z["n"];dll=z["cll"]/vn-z["bll"]/vn;dbr=z["cbr"]/vn-z["bbr"]/vn
        vdll[v]=dll;vdbr[v]=dbr;vll+=dll<0;vbr+=dbr<0
    out={"contract":"V5_LANE_CLASS_PLUS_OPPONENT_COMPOSITION_V1","period":{"start":START,"end":END},
         "candidate":{"baseline":["lane_number","racer_class"],"added":["opponent_lane_x_opponent_class composition residual"],"history":"strict previous calendar days","pair_effect":"empirical_bayes_shrink_to_current_lane_class_baseline","aggregation":"geometric_mean_of_five_opponent_ratios","parameter_search":False,"v4_opponent_logic_used":False,"same_day_results_used":False},
         "coverage":{"completed_races":len(races),"scored":n,"coverage_pct":100*n/len(races),"skipped":skip,"invalid_entry_rows":invalid,"matched_pair_pct":100*tot["matched"]/tot["pairs"] if tot["pairs"] else None,"mean_pair_shrink_weight":tot["ws"]/tot["wn"] if tot["wn"] else None,"venue_count":len(pv)},
         "metrics":{"baseline_logloss":bll,"candidate_logloss":cll,"delta_logloss":cll-bll,"baseline_brier":bbr,"candidate_brier":cbr,"delta_brier":cbr-bbr,"baseline_top1":tot["bh"]/n,"candidate_top1":tot["ch"]/n,"venues_better_logloss":vll,"venues_better_brier":vbr},
         "venue_delta_logloss":vdll,"venue_delta_brier":vdbr,
         "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False,"stake_change":False}}
    print("V5_LANE_CLASS_PLUS_OPPONENT_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
