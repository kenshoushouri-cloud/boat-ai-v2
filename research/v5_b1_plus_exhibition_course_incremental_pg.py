# -*- coding: utf-8 -*-
"""V5 B14H: exhibition-course incremental over B1 lane baseline."""
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
    ll=-math.log(max(p[w-1],EPS))
    y=[0.0]*6; y[w-1]=1.0
    br=sum((p[i]-y[i])**2 for i in range(6))
    m=max(p); tops=[i+1 for i,x in enumerate(p) if abs(x-m)<1e-15]
    return ll,br,int(len(tops)==1 and tops[0]==w)

def main():
    rc,xc,ec=cols("v2_races"),cols("v2_results"),cols("v2_realtime_exhibition_snapshots")
    if "exhibition_course" not in ec: raise RuntimeError("exhibition_course unavailable")
    we=winexpr(xc); ve=venueexpr(rc)
    fs=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc: fs.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc: fs.append("coalesce(rs.race_status,'official')='official'")
    races=fetch_all(f"""select r.race_id,r.race_date,{ve} venue,{we} winner
      from v2_races r join v2_results rs on rs.race_id=r.race_id
      where {' and '.join(fs)} order by r.race_date,r.race_id""",(START,END))

    xr=fetch_all("""select x.race_id,x.lane,x.exhibition_course
      from v2_realtime_exhibition_snapshots x join v2_races r on r.race_id=x.race_id
      where r.race_date between %s and %s and x.snapshot_label=%s
      order by r.race_date,x.race_id,x.lane,x.snapshot_at""",(START,END,LABEL))

    by=defaultdict(dict); invalid=0
    for x in xr:
        try:
            lane=int(x["lane"]); course=int(x["exhibition_course"])
        except Exception:
            invalid+=1; continue
        if lane not in range(1,7) or course not in range(1,7):
            invalid+=1; continue
        by[str(x["race_id"])][lane]=course

    days=defaultdict(list); missing=0; nonperm=0; changed=0
    for r in races:
        rid=str(r["race_id"]); m=by.get(rid,{})
        if len(m)!=6 or any(i not in m for i in range(1,7)):
            missing+=1; continue
        courses=[m[i] for i in range(1,7)]
        if sorted(courses)!=[1,2,3,4,5,6]:
            nonperm+=1; continue
        if any(m[i]!=i for i in range(1,7)): changed+=1
        days[iso(r["race_date"])].append(r)

    lane_w=Counter(); lane_n=0
    course_w=Counter(); course_n=0
    tot={"n":0,"bll":0.0,"bbr":0.0,"bh":0,"cll":0.0,"cbr":0.0,"ch":0,"changed_n":0,
         "changed_bll":0.0,"changed_bbr":0.0,"changed_cll":0.0,"changed_cbr":0.0}
    pv=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})

    for day in sorted(days):
        lp=probs(lane_w,lane_n)
        cp_base=probs(course_w,course_n)
        dlw=Counter(); dcw=Counter(); dn=0
        for r in days[day]:
            rid=str(r["race_id"]); winner=int(r["winner"]); m=by[rid]
            raw=[cp_base[m[lane]-1] for lane in range(1,7)]
            s=sum(raw); cp=[x/s for x in raw]
            bll,bbr,bh=score(lp,winner); cll,cbr,ch=score(cp,winner)
            tot["n"]+=1;tot["bll"]+=bll;tot["bbr"]+=bbr;tot["bh"]+=bh
            tot["cll"]+=cll;tot["cbr"]+=cbr;tot["ch"]+=ch
            ischg=any(m[i]!=i for i in range(1,7))
            if ischg:
                tot["changed_n"]+=1;tot["changed_bll"]+=bll;tot["changed_bbr"]+=bbr
                tot["changed_cll"]+=cll;tot["changed_cbr"]+=cbr
            v=str(r["venue"]); z=pv[v];z["n"]+=1;z["bll"]+=bll;z["bbr"]+=bbr;z["cll"]+=cll;z["cbr"]+=cbr
            dlw[winner]+=1
            dcw[m[winner]]+=1
            dn+=1
        lane_w.update(dlw); lane_n+=dn
        course_w.update(dcw); course_n+=dn

    n=tot["n"]
    if not n: raise RuntimeError("zero scoreable races")
    bll=tot["bll"]/n;bbr=tot["bbr"]/n;cll=tot["cll"]/n;cbr=tot["cbr"]/n
    vll=vbr=0; vdll={};vdbr={}
    for v,z in sorted(pv.items()):
        vn=z["n"]; dll=z["cll"]/vn-z["bll"]/vn; dbr=z["cbr"]/vn-z["bbr"]/vn
        vdll[v]=dll;vdbr[v]=dbr;vll+=dll<0;vbr+=dbr<0
    cn=tot["changed_n"]
    changed_metrics=None
    if cn:
        changed_metrics={
          "races":cn,
          "baseline_logloss":tot["changed_bll"]/cn,
          "candidate_logloss":tot["changed_cll"]/cn,
          "delta_logloss":tot["changed_cll"]/cn-tot["changed_bll"]/cn,
          "baseline_brier":tot["changed_bbr"]/cn,
          "candidate_brier":tot["changed_cbr"]/cn,
          "delta_brier":tot["changed_cbr"]/cn-tot["changed_bbr"]/cn
        }
    out={"contract":"V5_B1_PLUS_EXHIBITION_COURSE_V1","period":{"start":START,"end":END},
      "candidate":{"baseline":"B1 lane empirical previous-day win rate","added":"historical exhibition_course as course assignment","snapshot_label":LABEL,"same_day_results_used":False,"parameter_search":False,"v4_logic":False},
      "coverage":{"completed_races":len(races),"scored":n,"coverage_pct":100*n/len(races),"missing_complete6":missing,"non_permutation_excluded":nonperm,"invalid_rows":invalid,"course_changed_races":changed,"course_changed_pct":100*changed/n,"venue_count":len(pv)},
      "metrics":{"baseline_logloss":bll,"candidate_logloss":cll,"delta_logloss":cll-bll,"baseline_brier":bbr,"candidate_brier":cbr,"delta_brier":cbr-bbr,"baseline_top1":tot["bh"]/n,"candidate_top1":tot["ch"]/n,"venues_better_logloss":vll,"venues_better_brier":vbr},
      "course_changed_subset":changed_metrics,
      "venue_delta_logloss":vdll,"venue_delta_brier":vdbr,
      "provenance_caveat":"historical snapshot proves stored official beforeinfo values, not exact first operational availability time",
      "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False,"stake_change":False}}
    print("V5_B1_PLUS_EXHIBITION_COURSE_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))

if __name__=="__main__": main()
