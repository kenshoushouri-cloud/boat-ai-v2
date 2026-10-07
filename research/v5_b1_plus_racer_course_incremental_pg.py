# -*- coding: utf-8 -*-
"""V5 B7B: incremental racer-course compatibility over B1 lane baseline."""
from __future__ import annotations
import json,math,os
from collections import Counter,defaultdict
from datetime import date,datetime
from typing import Any
from db_pg import fetch_all

START=date.fromisoformat(os.getenv("START_DATE","2025-07-01"))
END=date.fromisoformat(os.getenv("END_DATE","2026-10-05"))
EPS=1e-12

def asdate(v:Any)->date:
    if isinstance(v,datetime): return v.date()
    if isinstance(v,date): return v
    return date.fromisoformat(str(v))
def ii(v:Any)->int:
    try:return int(v)
    except:return 0
def cols(t:str)->set[str]:
    return {str(r["column_name"]) for r in fetch_all(
        "select column_name from information_schema.columns where table_schema='public' and table_name=%s",(t,))}
def winner_expr(c:set[str])->str:
    if "first_lane" in c:return "rs.first_lane::int"
    return "nullif(substring(regexp_replace(rs.trifecta_ticket::text,'[^0-9]','','g') from 1 for 1),'')::int"
def venue_expr(c:set[str])->str:
    if "venue_id" in c and "venue_code" in c:
        return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
    return "lpad(r."+("venue_id" if "venue_id" in c else "venue_code")+"::text,2,'0')"
def lane_probs(w:Counter[int],n:int)->list[float]:
    return [(w[k]+1)/(n+6) for k in range(1,7)]
def metric(p:list[float],winner:int)->tuple[float,float,int]:
    ll=-math.log(max(p[winner-1],EPS)); y=[0.0]*6;y[winner-1]=1.0
    br=sum((p[k]-y[k])**2 for k in range(6))
    m=max(p);tops=[k+1 for k,x in enumerate(p) if abs(x-m)<1e-15]
    return ll,br,int(len(tops)==1 and tops[0]==winner)
def cprior(c:int,cs:Counter[int],ct:Counter[int])->float:
    return (ct[c]+1)/(cs[c]+2)
def cell(r:int,c:int,p:float,rs:dict[int,Counter[int]],rt:dict[int,Counter[int]])->tuple[float,int]:
    n=rs[c][r];return (rt[c][r]+2*p)/(n+2),n
def tau(c:int,p:float,rs:dict[int,Counter[int]],rt:dict[int,Counter[int]])->float:
    vals=[];sv=[]
    for r,n in rs[c].items():
        if n<1:continue
        x,_=cell(r,c,p,rs,rt);vals.append(x);sv.append(max(x*(1-x)/n,EPS))
    if len(vals)<2:return 0.0
    m=sum(vals)/len(vals)
    return max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(sv)/len(sv))
def adjusted(r:int,c:int,p:float,t:float,rs:dict[int,Counter[int]],rt:dict[int,Counter[int]])->tuple[float,int]:
    x,n=cell(r,c,p,rs,rt)
    if n<1 or t<=0:return p,n
    sv=max(x*(1-x)/n,EPS);w=t/(t+sv)
    return w*x+(1-w)*p,n

def main()->None:
    rc,ec,xc,rec=cols("v2_races"),cols("v2_race_entries"),cols("v2_results"),cols("v2_result_entries")
    we=winner_expr(xc);ve=venue_expr(rc)
    filt=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc:filt.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc:filt.append("coalesce(rs.race_status,'official')='official'")
    races=fetch_all(f"select r.race_id,r.race_date::date race_date,{ve} venue,{we} winner from v2_races r join v2_results rs on rs.race_id=r.race_id where {' and '.join(filt)} order by r.race_date,r.race_id",(START,END))
    entries=fetch_all("select e.race_id,r.race_date::date race_date,e.lane,e.racer_number from v2_race_entries e join v2_races r on r.race_id=e.race_id where r.race_date between %s and %s order by r.race_date,e.race_id,e.lane",(START,END))
    hist=fetch_all("select r.race_date::date race_date,re.racer_number,re.start_course,re.finish_position from v2_result_entries re join v2_races r on r.race_id=re.race_id where r.race_date between %s and %s and re.racer_number is not null order by r.race_date,re.race_id,re.lane",(START,END))
    wb={str(x["race_id"]):ii(x["winner"]) for x in races};db={str(x["race_id"]):asdate(x["race_date"]) for x in races};vb={str(x["race_id"]):str(x["venue"]) for x in races}
    rb=defaultdict(dict)
    for x in entries:
        rid=str(x["race_id"]);lane=ii(x["lane"]);racer=ii(x["racer_number"])
        if rid in wb and lane in range(1,7) and racer>0:rb[rid][lane]=racer
    hd=defaultdict(list)
    for x in hist:
        racer=ii(x["racer_number"]);c=ii(x["start_course"]);f=ii(x["finish_position"])
        if racer>0 and c in range(1,7) and f in range(1,7):hd[asdate(x["race_date"])].append((racer,c,f))
    days=defaultdict(list)
    for rid in wb:
        if len(rb[rid])==6 and all(k in rb[rid] for k in range(1,7)):days[db[rid]].append(rid)

    lw=Counter();ln=0
    cs=Counter();ct=Counter();rs={c:Counter() for c in range(1,7)};rt={c:Counter() for c in range(1,7)}
    tot={"n":0,"bll":0.0,"bbr":0.0,"bh":0,"cll":0.0,"cbr":0.0,"ch":0}
    pv=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})
    nop=0;obs=0
    for day in sorted(days):
        bp=lane_probs(lw,ln)
        pr={c:cprior(c,cs,ct) for c in range(1,7)}
        tv={c:tau(c,pr[c],rs,rt) for c in range(1,7)}
        daywins=Counter()
        for rid in days[day]:
            rel=[]
            for lane in range(1,7):
                a,n=adjusted(rb[rid][lane],lane,pr[lane],tv[lane],rs,rt)
                rel.append(max(a/max(pr[lane],EPS),EPS));obs+=1;nop+=n==0
            raw=[bp[k]*rel[k] for k in range(6)];s=sum(raw);cp=[x/s for x in raw]
            w=wb[rid];bll,bbr,bh=metric(bp,w);cll,cbr,ch=metric(cp,w)
            tot["n"]+=1;tot["bll"]+=bll;tot["bbr"]+=bbr;tot["bh"]+=bh;tot["cll"]+=cll;tot["cbr"]+=cbr;tot["ch"]+=ch
            z=pv[vb[rid]];z["n"]+=1;z["bll"]+=bll;z["bbr"]+=bbr;z["cll"]+=cll;z["cbr"]+=cbr
            daywins[w]+=1
        lw.update(daywins);ln+=sum(daywins.values())
        for racer,c,f in hd.get(day,[]):
            cs[c]+=1;rs[c][racer]+=1
            if f<=3:ct[c]+=1;rt[c][racer]+=1
    n=tot["n"];bll=tot["bll"]/n;bbr=tot["bbr"]/n;cll=tot["cll"]/n;cbr=tot["cbr"]/n
    dl={};dbri={};vll=vbr=0
    for v,z in sorted(pv.items()):
        vn=z["n"];x=z["cll"]/vn-z["bll"]/vn;y=z["cbr"]/vn-z["bbr"]/vn
        dl[v]=x;dbri[v]=y;vll+=x<0;vbr+=y<0
    out={"contract":"V5_B1_PLUS_RACER_COURSE_INCREMENTAL_V1","period":{"start":str(START),"end":str(END)},
         "candidate":{"baseline":["lane_number"],"added":["prior_day_racer_x_course_top3_residual"],"formula":"p proportional to B1_lane_p * (shrunk_racer_course_top3/course_population_top3)","parameter_search":False,"same_day_results_used":False,"v4_logic":False},
         "coverage":{"races":n,"venue_count":len(pv),"no_prior_racer_course_pct":100*nop/obs if obs else None},
         "metrics":{"b1_logloss":bll,"candidate_logloss":cll,"delta_logloss":cll-bll,"b1_brier":bbr,"candidate_brier":cbr,"delta_brier":cbr-bbr,"b1_top1":tot["bh"]/n,"candidate_top1":tot["ch"]/n,"venues_better_logloss":vll,"venues_better_brier":vbr},
         "venue_delta_logloss":dl,"venue_delta_brier":dbri,
         "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False}}
    print("V5_B1_PLUS_RACER_COURSE_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
