# -*- coding: utf-8 -*-
"""Descriptive robustness audit for frozen S03_M2_POSITIVE_V1 Forward evidence.

No filtering, subgroup selection, threshold search, or retuning is performed.
The exact frozen positive-score observations are stress-tested by deterministic
leave-one-hit-out / leave-one-day-out and chronological summaries.
"""
from __future__ import annotations
import json, math, os, re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import psycopg
from psycopg.rows import dict_row

START=date(2026,9,13)
END=date(2026,9,27)
UNIT=100
JST=ZoneInfo("Asia/Tokyo")
W=(1.0,0.6,0.3)
OUTPUT=Path(os.getenv("S03_ROBUST_OUTPUT","s03-forward-descriptive-robustness.json"))

def si(v:Any,d=0):
    try:return int(float(v)) if v not in (None,"") else d
    except:return d
def sf(v:Any):
    try:return float(v) if v not in (None,"") else None
    except:return None
def jt(v:Any):
    if not isinstance(v,datetime):return None
    if v.tzinfo is None:v=v.replace(tzinfo=JST)
    return v.astimezone(JST)
def lanes(t:Any):
    xs=[int(x) for x in re.findall(r"[1-6]",str(t or ""))]
    return tuple(xs[:3]) if len(xs)>=3 and len(set(xs[:3]))==3 else None
def score(entries,ticket):
    ls=lanes(ticket); by={si(e.get("lane")):e for e in entries}
    if ls is None or set(by)!={1,2,3,4,5,6}:return None
    vals=[]
    for lane in range(1,7):
        x=sf(by[lane].get("motor_place2_rate"))
        if x is None or not 0<=x<=100:return None
        vals.append(x)
    mu=sum(vals)/6; sd=math.sqrt(sum((x-mu)**2 for x in vals)/6)
    if sd<1e-12:return None
    z={i+1:(vals[i]-mu)/sd for i in range(6)}
    a,b,c=ls
    return W[0]*z[a]+W[1]*z[b]+W[2]*z[c]
def settled(r):
    return str(r.get("evaluation_status") or "")=="evaluated" and r.get("hit") is not None and r.get("return_yen") is not None
def metrics(rows):
    rr=sorted([r for r in rows if settled(r)],key=lambda r:(str(r["race_date"]),str(r["race_id"])))
    inv=len(rr)*UNIT
    gross=sum(si(r.get("return_yen")) if bool(r.get("hit")) else 0 for r in rr)
    hits=sum(int(bool(r.get("hit"))) for r in rr)
    return {"n":len(rr),"hits":hits,"investment_yen":inv,"return_yen":gross,
            "profit_yen":gross-inv,"roi_pct":round(gross/inv*100,4) if inv else None}
def main():
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:raise RuntimeError("DATABASE_URL required")
    print("S03_ROBUST_POLICY=DESCRIPTIVE_STRESS_TEST_NO_SUBGROUP_SELECTION",flush=True)
    print("S03_ROBUST_RETUNE=0 FILTER_SEARCH=0",flush=True)
    print("S03_ROBUST_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0",flush=True)
    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("""select s.race_id,s.race_date,s.ticket,s.snapshot_at,s.hit,s.return_yen,
                                  s.evaluation_status,r.deadline_at
                             from v2_candidate_filter_shadow s
                             join v2_races r on r.race_id=s.race_id
                            where s.rule_id='S03' and s.race_date between %s and %s
                            order by s.race_date,s.race_id""",(START,END))
            rows=[dict(r) for r in cur.fetchall()]
            ids=sorted({str(r["race_id"]) for r in rows})
            ent=defaultdict(list)
            if ids:
                cur.execute("""select race_id,lane,motor_place2_rate from v2_race_entries
                                where race_id=any(%s) order by race_id,lane""",(ids,))
                for r in cur.fetchall():ent[str(r["race_id"])].append(dict(r))
        conn.rollback()
    positive=[]
    for r in rows:
        snap=jt(r.get("snapshot_at")); deadline=jt(r.get("deadline_at"))
        if snap is None or deadline is None or snap>=deadline:continue
        s=score(ent.get(str(r["race_id"]),[]),r.get("ticket"))
        if s is not None and s>0:
            x=dict(r);x["motor2_score"]=s;positive.append(x)
    ev=sorted([r for r in positive if settled(r)],key=lambda r:(str(r["race_date"]),str(r["race_id"])))
    overall=metrics(ev)

    hit_rows=[r for r in ev if bool(r.get("hit"))]
    leave_hit=[]
    for h in hit_rows:
        remain=[r for r in ev if str(r["race_id"])!=str(h["race_id"])]
        leave_hit.append({"removed_race_id":str(h["race_id"]),"removed_return_yen":si(h.get("return_yen")),**metrics(remain)})
    leave_hit.sort(key=lambda x:(x["roi_pct"] if x["roi_pct"] is not None else -1,x["removed_race_id"]))

    days=sorted({str(r["race_date"]) for r in ev})
    leave_day=[]
    for d in days:
        remain=[r for r in ev if str(r["race_date"])!=d]
        leave_day.append({"removed_date":d,**metrics(remain)})
    leave_day.sort(key=lambda x:(x["roi_pct"] if x["roi_pct"] is not None else -1,x["removed_date"]))

    mid=len(ev)//2
    halves={"first":metrics(ev[:mid]),"second":metrics(ev[mid:])}

    checkpoints=[]
    for n in (10,20,30,40,50,len(ev)):
        if n<=0 or n>len(ev):continue
        if any(x["n"]==n for x in checkpoints):continue
        checkpoints.append({"n":n,**metrics(ev[:n])})

    by_day=[]
    profitable_days=0
    for d in days:
        dm=metrics([r for r in ev if str(r["race_date"])==d])
        profitable_days+=int(dm["profit_yen"]>0)
        by_day.append({"date":d,**dm})

    out={"contract":"s03_m2_positive_v1_forward_descriptive_robustness_v1",
         "period":{"start":START.isoformat(),"end":END.isoformat()},
         "overall":overall,
         "chronological_halves":halves,
         "cumulative_checkpoints":checkpoints,
         "leave_one_hit_out":leave_hit,
         "leave_one_hit_out_min_roi_pct":min((x["roi_pct"] for x in leave_hit),default=None),
         "leave_one_day_out_worst":leave_day[0] if leave_day else None,
         "active_days":len(days),"profitable_days":profitable_days,
         "profitable_day_rate_pct":round(profitable_days/len(days)*100,4) if days else None,
         "by_day":by_day,
         "interpretation_limits":{
             "descriptive_only":True,
             "no_date_filter_may_be_created_from_this":True,
             "no_hit_removal_is_a_real_policy":True,
             "no_retune":True,
         },
         "safety":{"db_write":False,"line":False,"buy":False,"production_change":False,"promotion_allowed":False}}
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("S03_ROBUST_OVERALL="+json.dumps(overall,sort_keys=True),flush=True)
    print("S03_ROBUST_HALVES="+json.dumps(halves,sort_keys=True),flush=True)
    print("S03_ROBUST_LEAVE_ONE_HIT_MIN_ROI="+str(out["leave_one_hit_out_min_roi_pct"]),flush=True)
    print("S03_ROBUST_LEAVE_ONE_DAY_WORST="+json.dumps(out["leave_one_day_out_worst"],sort_keys=True),flush=True)
    print("S03_ROBUST_PROFITABLE_DAYS="+f"{profitable_days}/{len(days)}",flush=True)
    print("S03_ROBUST_CUMULATIVE="+json.dumps(checkpoints,sort_keys=True),flush=True)
    print("S03_ROBUST_PROMOTION_ALLOWED=0",flush=True)
    print("S03_ROBUST_RESULT=PASS_READ_ONLY",flush=True)
if __name__=="__main__":main()
