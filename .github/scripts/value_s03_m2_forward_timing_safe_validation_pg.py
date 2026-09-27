# -*- coding: utf-8 -*-
"""Strict timing-safe validation of frozen S03_M2_POSITIVE_V1 Forward checkpoint.

Selection rule is unchanged. This audit only strengthens evidence validity by
requiring stored snapshot_at < deadline_at, then reports robustness metrics.
"""
from __future__ import annotations
import json, math, os, random, re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import psycopg
from psycopg.rows import dict_row

START=date(2026,9,13)
END=date(2026,9,27)
JST=ZoneInfo("Asia/Tokyo")
W=(1.0,0.6,0.3)
UNIT=100
SAMPLES=20000
SEED=20260927
OUTPUT=Path(os.getenv("S03_FORWARD_VALIDATION_OUTPUT","s03-forward-timing-safe-validation.json"))

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
def settled(r):return r.get("hit") is not None and r.get("return_yen") is not None
def metrics(rows):
    rr=sorted([r for r in rows if settled(r)],key=lambda r:(str(r["race_date"]),str(r["race_id"])))
    inv=len(rr)*UNIT; gross=0; hits=0; vals=[]; run=peak=dd=loss=maxloss=0
    for r in rr:
        ret=si(r.get("return_yen")) if bool(r.get("hit")) else 0
        gross+=ret; hits+=int(ret>0)
        if ret>0: vals.append(ret); loss=0
        else: loss+=1; maxloss=max(maxloss,loss)
        run+=ret-UNIT; peak=max(peak,run); dd=max(dd,peak-run)
    vals.sort(reverse=True)
    return {"evaluated":len(rr),"hits":hits,"investment_yen":inv,"return_yen":gross,
            "profit_yen":gross-inv,"roi_pct":round(gross/inv*100,4) if inv else None,
            "largest_hit_yen":vals[0] if vals else 0,
            "largest_hit_share_pct":round(vals[0]/gross*100,4) if vals and gross else 0.0,
            "max_drawdown_yen":dd,"max_losing_streak":maxloss}
def bootstrap(rows):
    by=defaultdict(list)
    for r in rows:
        if settled(r):by[str(r["race_date"])].append(r)
    days=sorted(by)
    if not days:return {"samples":0}
    rnd=random.Random(SEED); rois=[]
    for _ in range(SAMPLES):
        inv=gross=0
        for _d in days:
            d=days[rnd.randrange(len(days))]
            for r in by[d]:
                inv+=UNIT
                if bool(r.get("hit")):gross+=si(r.get("return_yen"))
        rois.append(gross/inv*100 if inv else 0)
    rois.sort(); n=len(rois)
    return {"samples":n,"seed":SEED,"median_roi_pct":round(rois[n//2],4),
            "ci95_roi_pct":[round(rois[int(.025*(n-1))],4),round(rois[int(.975*(n-1))],4)],
            "p_roi_gt_100_pct":round(sum(x>100 for x in rois)/n*100,4)}
def monthly(rows):
    by=defaultdict(list)
    for r in rows:
        if settled(r):by[str(r["race_date"])[:7]].append(r)
    return [{"month":m,**metrics(rr)} for m,rr in sorted(by.items())]

def main():
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:raise RuntimeError("DATABASE_URL required")
    print("S03_FORWARD_VALIDATION_POLICY=FROZEN_RULE_STRICT_PREDEADLINE_ONLY",flush=True)
    print("S03_FORWARD_VALIDATION_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0",flush=True)
    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("""select s.race_id,s.race_date,s.ticket,s.snapshot_at,s.hit,s.return_yen,r.deadline_at
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
    timing_valid=[]; late=[]; missing=0; positive=[]
    margins=[]
    for r in rows:
        snap=jt(r.get("snapshot_at")); deadline=jt(r.get("deadline_at"))
        if snap is None or deadline is None or snap>=deadline:
            late.append(r); continue
        timing_valid.append(r); margins.append((deadline-snap).total_seconds()/60)
        s=score(ent.get(str(r["race_id"]),[]),r.get("ticket"))
        if s is None:missing+=1; continue
        if s>0:
            x=dict(r);x["motor2_score"]=s;positive.append(x)
    out={"contract":"s03_m2_positive_v1_forward_timing_safe_checkpoint_v1",
         "period":{"start":START.isoformat(),"end":END.isoformat()},
         "coverage":{"source_s03_rows":len(rows),"timing_valid_rows":len(timing_valid),
                     "late_or_unknown_rows":len(late),"missing_motor_rows":missing,
                     "positive_rows":len(positive),
                     "min_minutes_before_deadline":round(min(margins),3) if margins else None},
         "timing_safe_positive":{"overall":metrics(positive),"monthly":monthly(positive),"day_bootstrap":bootstrap(positive)},
         "checkpoints":{"30":len([r for r in positive if settled(r)])>=30,
                        "50":len([r for r in positive if settled(r)])>=50,
                        "100":len([r for r in positive if settled(r)])>=100},
         "safety":{"fixed_rule":True,"db_write":False,"line":False,"buy":False,
                   "production_change":False,"promotion_allowed":False}}
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("S03_FORWARD_VALIDATION_RESULT_JSON="+json.dumps(out,sort_keys=True),flush=True)
    print("S03_FORWARD_VALIDATION_PROMOTION_ALLOWED=0",flush=True)
    print("S03_FORWARD_VALIDATION_RESULT=PASS_READ_ONLY",flush=True)
if __name__=="__main__":main()
