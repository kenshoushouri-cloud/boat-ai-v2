# -*- coding: utf-8 -*-
"""Strict timing-safe checkpoint for frozen S02_FORWARD_V1."""
from __future__ import annotations
import json, os, random
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
SAMPLES=20000
SEED=20260927
JST=ZoneInfo("Asia/Tokyo")
OUTPUT=Path(os.getenv("S02_FORWARD_OUTPUT","s02-forward-timing-safe-checkpoint.json"))

def si(v:Any,d=0):
    try:return int(float(v)) if v not in (None,"") else d
    except:return d
def jt(v:Any):
    if not isinstance(v,datetime):return None
    if v.tzinfo is None:v=v.replace(tzinfo=JST)
    return v.astimezone(JST)
def settled(r):return r.get("hit") is not None and r.get("return_yen") is not None
def metrics(rows):
    rr=sorted([r for r in rows if settled(r)],key=lambda r:(str(r["race_date"]),str(r["race_id"])))
    inv=len(rr)*UNIT; gross=hits=0; vals=[]; eq=peak=dd=loss=maxloss=0
    for r in rr:
        ret=si(r.get("return_yen")) if bool(r.get("hit")) else 0
        gross+=ret; hits+=int(ret>0)
        if ret>0: vals.append(ret); loss=0
        else: loss+=1; maxloss=max(maxloss,loss)
        eq+=ret-UNIT; peak=max(peak,eq); dd=max(dd,peak-eq)
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
    rois.sort();n=len(rois)
    return {"samples":n,"seed":SEED,"median_roi_pct":round(rois[n//2],4),
            "ci95_roi_pct":[round(rois[int(.025*(n-1))],4),round(rois[int(.975*(n-1))],4)],
            "p_roi_gt_100_pct":round(sum(x>100 for x in rois)/n*100,4)}
def halves(rows):
    rr=sorted([r for r in rows if settled(r)],key=lambda r:(str(r["race_date"]),str(r["race_id"])))
    mid=len(rr)//2
    return {"first":metrics(rr[:mid]),"second":metrics(rr[mid:])}

def main():
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:raise RuntimeError("DATABASE_URL required")
    print("S02_FORWARD_POLICY=FROZEN_S02_STRICT_PREDEADLINE_NO_RETUNE",flush=True)
    print("S02_FORWARD_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0",flush=True)
    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("""select s.race_id,s.race_date,s.window_name,s.ticket,s.snapshot_at,
                                  s.hit,s.return_yen,s.evaluated_at,r.deadline_at
                             from v2_candidate_filter_shadow s
                             join v2_races r on r.race_id=s.race_id
                            where s.rule_id='S02' and s.race_date between %s and %s
                            order by s.race_date,s.race_id""",(START,END))
            rows=[dict(r) for r in cur.fetchall()]
        conn.rollback()
    valid=[];late=[];margins=[]
    for r in rows:
        snap=jt(r.get("snapshot_at"));deadline=jt(r.get("deadline_at"))
        if snap is None or deadline is None or snap>=deadline:late.append(r);continue
        valid.append(r);margins.append((deadline-snap).total_seconds()/60)
    m=metrics(valid)
    out={"contract":"S02_FORWARD_V1_timing_safe_checkpoint",
         "period":{"start":START.isoformat(),"end":END.isoformat()},
         "coverage":{"source_rows":len(rows),"timing_valid_rows":len(valid),"late_or_unknown_rows":len(late),
                     "min_minutes_before_deadline":round(min(margins),3) if margins else None},
         "forward":{"overall":m,"chronological_halves":halves(valid),"day_bootstrap":bootstrap(valid)},
         "checkpoints":{"30":m["evaluated"]>=30,"50":m["evaluated"]>=50,"100":m["evaluated"]>=100},
         "safety":{"db_write":False,"line":False,"buy":False,"production_change":False,"promotion_allowed":False}}
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("S02_FORWARD_RESULT_JSON="+json.dumps(out,sort_keys=True),flush=True)
    print("S02_FORWARD_PROMOTION_ALLOWED=0",flush=True)
    print("S02_FORWARD_RESULT=PASS_READ_ONLY",flush=True)
if __name__=="__main__":main()
