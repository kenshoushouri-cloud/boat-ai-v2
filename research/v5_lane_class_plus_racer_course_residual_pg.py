# -*- coding: utf-8 -*-
"""V5 core incremental: lane+class baseline plus racer-course residual."""
from __future__ import annotations
import json,math,os
from collections import Counter,defaultdict
from datetime import date,datetime
from typing import Any
from db_pg import fetch_all

START=date.fromisoformat(os.getenv("START_DATE","2025-07-01"))
END=date.fromisoformat(os.getenv("END_DATE","2026-10-05"))
EPS=1e-12; ALPHA=1.0

def d(v:Any)->date:
    if isinstance(v,datetime): return v.date()
    if isinstance(v,date): return v
    return date.fromisoformat(str(v))
def cols(t):
    return {str(r["column_name"]) for r in fetch_all("select column_name from information_schema.columns where table_schema='public' and table_name=%s",(t,))}
def i(v):
    try:return int(v)
    except:return None
def clean(v):
    if v is None:return None
    s=str(v).strip().upper()
    return s or None
def winexpr(c):
    if "first_lane" in c:return "rs.first_lane::int"
    return "nullif(substring(regexp_replace(rs.trifecta_ticket::text,'[^0-9]','','g') from 1 for 1),'')::int"
def venueexpr(c):
    if "venue_id" in c and "venue_code" in c:return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
    if "venue_id" in c:return "lpad(r.venue_id::text,2,'0')"
    if "venue_code" in c:return "lpad(r.venue_code::text,2,'0')"
    return "'NA'"
def lane_probs(w,n):
    den=n+6*ALPHA
    return [(w[k]+ALPHA)/den for k in range(1,7)]
def score(p,w):
    ll=-math.log(max(p[w-1],EPS)); y=[0.0]*6; y[w-1]=1.0
    br=sum((p[j]-y[j])**2 for j in range(6))
    m=max(p);tops=[j+1 for j,x in enumerate(p) if abs(x-m)<1e-15]
    return ll,br,int(len(tops)==1 and tops[0]==w)
def lc_probs(classes,lp,starts,wins):
    raw=[]
    for lane in range(1,7):
        prior=lp[lane-1]; vals=[]; svars=[]
        for cls,n in starts[lane].items():
            if n<=0: continue
            r=(wins[lane][cls]+2*prior)/(n+2)
            vals.append(r); svars.append(max(r*(1-r)/n,EPS))
        tau=0.0
        if len(vals)>=2:
            m=sum(vals)/len(vals)
            tau=max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(svars)/len(svars))
        cls=classes[lane]; n=starts[lane][cls]
        r=(wins[lane][cls]+2*prior)/(n+2)
        wt=0.0 if n<=0 or tau<=0 else tau/(tau+max(r*(1-r)/n,EPS))
        raw.append(max(wt*r+(1-wt)*prior,EPS))
    s=sum(raw); return [x/s for x in raw]
def course_prior(c,starts,top3):
    return (top3[c]+1.0)/(starts[c]+2.0)
def rc_adjust(racer,c,prior,starts,top3):
    vals=[];svars=[]
    for rr,n in starts[c].items():
        if n<=0:continue
        rate=(top3[c][rr]+2*prior)/(n+2)
        vals.append(rate);svars.append(max(rate*(1-rate)/n,EPS))
    tau=0.0
    if len(vals)>=2:
        m=sum(vals)/len(vals)
        tau=max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(svars)/len(svars))
    n=starts[c][racer]; rate=(top3[c][racer]+2*prior)/(n+2)
    wt=0.0 if n<=0 or tau<=0 else tau/(tau+max(rate*(1-rate)/n,EPS))
    q=max(wt*rate+(1-wt)*prior,EPS)
    return q,n,wt

def main():
    rc,ec,xc,rec=cols("v2_races"),cols("v2_race_entries"),cols("v2_results"),cols("v2_result_entries")
    if {"lane","racer_number","racer_class"}-ec: raise RuntimeError("entry columns unavailable")
    if {"racer_number","start_course","finish_position"}-rec: raise RuntimeError("result entry columns unavailable")
    we=winexpr(xc);ve=venueexpr(rc)
    fs=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc:fs.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc:fs.append("coalesce(rs.race_status,'official')='official'")
    races=fetch_all(f"""select r.race_id,r.race_date::date race_date,{ve} venue,{we} winner
      from v2_races r join v2_results rs on rs.race_id=r.race_id
      where {' and '.join(fs)} order by r.race_date,r.race_id""",(START,END))
    entries=fetch_all("""select e.race_id,e.lane,e.racer_number,e.racer_class,r.race_date::date race_date
      from v2_race_entries e join v2_races r on r.race_id=e.race_id
      where r.race_date between %s and %s order by r.race_date,e.race_id,e.lane""",(START,END))
    hist=fetch_all("""select re.racer_number,re.start_course,re.finish_position,r.race_date::date race_date
      from v2_result_entries re join v2_races r on r.race_id=re.race_id
      where r.race_date between %s and %s and re.racer_number is not null
      order by r.race_date,re.race_id,re.lane""",(START,END))

    wb={str(r["race_id"]):int(r["winner"]) for r in races}
    db={str(r["race_id"]):d(r["race_date"]) for r in races}
    vb={str(r["race_id"]):str(r["venue"]) for r in races}
    by=defaultdict(dict);invalid=0
    for e in entries:
        rid=str(e["race_id"])
        if rid not in wb:continue
        lane=i(e["lane"]);racer=i(e["racer_number"]);cls=clean(e["racer_class"])
        if lane not in range(1,7) or racer is None or racer<=0 or cls is None:
            invalid+=1;continue
        by[rid][lane]=(racer,cls)
    days=defaultdict(list);skip=0
    for rid in wb:
        if len(by[rid])==6 and all(k in by[rid] for k in range(1,7)):days[db[rid]].append(rid)
        else:skip+=1
    hday=defaultdict(list);badh=0
    for h in hist:
        racer=i(h["racer_number"]);c=i(h["start_course"]);f=i(h["finish_position"])
        if racer is None or racer<=0 or c not in range(1,7) or f not in range(1,7):
            badh+=1;continue
        hday[d(h["race_date"])].append((racer,c,f))

    lw=Counter();ln=0
    lcs={k:Counter() for k in range(1,7)};lcw={k:Counter() for k in range(1,7)}
    cs=Counter();ct=Counter();rcs={k:Counter() for k in range(1,7)};rct={k:Counter() for k in range(1,7)}
    tot={"n":0,"bll":0.0,"bbr":0.0,"bh":0,"cll":0.0,"cbr":0.0,"ch":0,"obs":0,"noprior":0,"ws":0.0}
    pv=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})

    for day in sorted(days):
        lp=lane_probs(lw,ln)
        dlw=Counter();dlcs={k:Counter() for k in range(1,7)};dlcw={k:Counter() for k in range(1,7)}
        priors={c:course_prior(c,cs,ct) for c in range(1,7)}
        for rid in days[day]:
            classes={lane:by[rid][lane][1] for lane in range(1,7)}
            bp=lc_probs(classes,lp,lcs,lcw)
            raw=[]
            for lane in range(1,7):
                racer,_=by[rid][lane]
                q,n,wt=rc_adjust(racer,lane,priors[lane],rcs,rct)
                residual=q/max(priors[lane],EPS)
                raw.append(max(bp[lane-1]*residual,EPS))
                tot["obs"]+=1;tot["noprior"]+=int(n==0);tot["ws"]+=wt
            s=sum(raw);cp=[x/s for x in raw];w=wb[rid]
            bll,bbr,bh=score(bp,w);cll,cbr,ch=score(cp,w)
            tot["n"]+=1;tot["bll"]+=bll;tot["bbr"]+=bbr;tot["bh"]+=bh
            tot["cll"]+=cll;tot["cbr"]+=cbr;tot["ch"]+=ch
            z=pv[vb[rid]];z["n"]+=1;z["bll"]+=bll;z["bbr"]+=bbr;z["cll"]+=cll;z["cbr"]+=cbr
            dlw[w]+=1
            for lane in range(1,7):
                cls=by[rid][lane][1];dlcs[lane][cls]+=1
            wcls=by[rid][w][1];dlcw[w][wcls]+=1
        lw.update(dlw);ln+=sum(dlw.values())
        for lane in range(1,7):lcs[lane].update(dlcs[lane]);lcw[lane].update(dlcw[lane])
        for racer,c,f in hday.get(day,[]):
            cs[c]+=1;rcs[c][racer]+=1
            if f<=3:ct[c]+=1;rct[c][racer]+=1

    n=tot["n"];bll=tot["bll"]/n;bbr=tot["bbr"]/n;cll=tot["cll"]/n;cbr=tot["cbr"]/n
    vll=vbr=0;vdll={};vdbr={}
    for v,z in sorted(pv.items()):
        vn=z["n"];dll=z["cll"]/vn-z["bll"]/vn;dbr=z["cbr"]/vn-z["bbr"]/vn
        vdll[v]=dll;vdbr[v]=dbr;vll+=dll<0;vbr+=dbr<0
    out={"contract":"V5_LANE_CLASS_PLUS_RACER_COURSE_RESIDUAL_V1","period":{"start":START.isoformat(),"end":END.isoformat()},
      "candidate":{"baseline":["lane_number","racer_class"],"added":"racer x actual-course historical top3 residual vs course population","target_course_proxy":"entry_lane","strictly_prior_calendar_day":True,"same_day_results_used":False,"parameter_search":False,"v4_logic":False},
      "coverage":{"completed_races":len(races),"scored":n,"coverage_pct":100*n/len(races),"skipped":skip,"invalid_entry_rows":invalid,"invalid_history_rows":badh,"lane_observations":tot["obs"],"no_prior_pct":100*tot["noprior"]/tot["obs"] if tot["obs"] else None,"mean_rc_shrink_weight":tot["ws"]/tot["obs"] if tot["obs"] else None,"venue_count":len(pv)},
      "metrics":{"baseline_logloss":bll,"candidate_logloss":cll,"delta_logloss":cll-bll,"baseline_brier":bbr,"candidate_brier":cbr,"delta_brier":cbr-bbr,"baseline_top1":tot["bh"]/n,"candidate_top1":tot["ch"]/n,"venues_better_logloss":vll,"venues_better_brier":vbr},
      "venue_delta_logloss":vdll,"venue_delta_brier":vdbr,
      "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False,"stake_change":False}}
    print("V5_LANE_CLASS_PLUS_RACER_COURSE_RESIDUAL_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
