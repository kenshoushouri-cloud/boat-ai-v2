# -*- coding: utf-8 -*-
"""V5 B9A: exhibition start-timing rank only, historical beforeinfo, read-only."""
from __future__ import annotations
import json,math,os
from collections import defaultdict
from typing import Any
from db_pg import fetch_all

START=os.getenv("START_DATE","2025-07-01")
END=os.getenv("END_DATE","2026-10-05")
LABEL="historical"
EPS=1e-15
B0LL=-math.log(1/6); B0BR=5/6

def cols(t):
    return {str(r["column_name"]) for r in fetch_all(
        "select column_name from information_schema.columns where table_schema='public' and table_name=%s",(t,))}
def winexpr(c):
    if "first_lane" in c:return "rs.first_lane::int"
    return "nullif(substring(regexp_replace(rs.trifecta_ticket::text,'[^0-9]','','g') from 1 for 1),'')::int"
def venueexpr(c):
    if "venue_id" in c and "venue_code" in c:
        return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
    if "venue_id" in c:return "lpad(r.venue_id::text,2,'0')"
    return "lpad(r.venue_code::text,2,'0')"
def ii(v):
    try:return int(v)
    except:return 0
def score(p,w):
    ll=-math.log(max(p[w-1],EPS));y=[0.0]*6;y[w-1]=1.0
    br=sum((p[k]-y[k])**2 for k in range(6))
    m=max(p);tops=[k+1 for k,x in enumerate(p) if abs(x-m)<1e-15]
    return ll,br,int(len(tops)==1 and tops[0]==w)

def main():
    rc,xc,ec=cols("v2_races"),cols("v2_results"),cols("v2_realtime_exhibition_snapshots")
    if "start_timing_rank" not in ec:raise RuntimeError("start_timing_rank unavailable")
    we=winexpr(xc);ve=venueexpr(rc)
    fs=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc:fs.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc:fs.append("coalesce(rs.race_status,'official')='official'")
    races=fetch_all(f"select r.race_id,{ve} venue,{we} winner from v2_races r join v2_results rs on rs.race_id=r.race_id where {' and '.join(fs)} order by r.race_id",(START,END))
    xs=fetch_all("""select x.race_id,x.lane,x.start_timing_rank
      from v2_realtime_exhibition_snapshots x
      join v2_races r on r.race_id=x.race_id
      where r.race_date between %s and %s and x.snapshot_label=%s
      order by x.race_id,x.lane""",(START,END,LABEL))
    rb=defaultdict(dict);invalid=0
    for x in xs:
        lane=ii(x["lane"]);rank=ii(x["start_timing_rank"])
        if lane not in range(1,7) or rank not in range(1,7):invalid+=1;continue
        rb[str(x["race_id"])][lane]=rank
    ll=br=0.0;hit=uniq=scored=0;skip=0
    pv=defaultdict(lambda:{"n":0,"ll":0.0,"br":0.0})
    for r in races:
        rid=str(r["race_id"]);vals=rb.get(rid,{})
        if len(vals)!=6 or any(k not in vals for k in range(1,7)):
            skip+=1;continue
        raw=[7.0-vals[k] for k in range(1,7)]
        s=sum(raw);p=[x/s for x in raw]
        w=ii(r["winner"]);a,b,h=score(p,w);ll+=a;br+=b;scored+=1
        m=max(p);tops=[k+1 for k,x in enumerate(p) if abs(x-m)<1e-15]
        if len(tops)==1:uniq+=1;hit+=h
        z=pv[str(r["venue"])];z["n"]+=1;z["ll"]+=a;z["br"]+=b
    if scored==0:raise RuntimeError("zero scoreable races")
    ml=ll/scored;mb=br/scored;vm={};vll=vbr=0
    for v,z in sorted(pv.items()):
        vl=z["ll"]/z["n"];vb=z["br"]/z["n"]
        vm[v]={"races":z["n"],"logloss":vl,"brier":vb,"delta_logloss_vs_b0":vl-B0LL,"delta_brier_vs_b0":vb-B0BR}
        vll+=vl<B0LL;vbr+=vb<B0BR
    out={"contract":"V5_ZERO_BASE_B9A_EXHIBITION_ST_RANK_ONLY_V1",
         "period":{"start":START,"end":END},
         "feature":{"input":"v2_realtime_exhibition_snapshots.start_timing_rank","snapshot_label":LABEL,"formula":"p proportional to 7-start_timing_rank","parameter_search":False,"result_or_odds_used":False,"v4_logic":False},
         "coverage":{"completed_result_races":len(races),"scored_complete6_races":scored,"coverage_pct":100*scored/len(races),"skipped_incomplete6":skip,"invalid_rows":invalid,"venue_count":len(pv)},
         "metrics":{"logloss":ml,"brier":mb,"delta_logloss_vs_b0":ml-B0LL,"delta_brier_vs_b0":mb-B0BR,"top1_unique":hit/uniq if uniq else None,"unique_top_races":uniq,"venues_better_logloss":vll,"venues_better_brier":vbr},
         "venue_metrics":vm,
         "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False,"stake_change":False}}
    print("V5_B9A_EXHIBITION_ST_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
