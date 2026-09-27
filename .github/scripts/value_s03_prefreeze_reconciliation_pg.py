# -*- coding: utf-8 -*-
"""Reconcile the original 2026-08-14..2026-09-12 S03 M2 pre-freeze evidence
against an explicit stored snapshot_at < deadline_at timing guard.
Read-only diagnostic only; no rule tuning.
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

START=date(2026,8,14)
END=date(2026,9,12)
JST=ZoneInfo("Asia/Tokyo")
W=(1.0,0.6,0.3)
OUTPUT=Path(os.getenv("S03_RECON_OUTPUT","s03-prefreeze-reconciliation.json"))

def si(v:Any,d=0):
    try:return int(float(v)) if v not in (None,"") else d
    except:return d
def sf(v:Any):
    try:return float(v) if v not in (None,"") else None
    except:return None
def jt(v:Any):
    if not isinstance(v,datetime): return None
    if v.tzinfo is None:v=v.replace(tzinfo=JST)
    return v.astimezone(JST)
def lanes(t:Any):
    xs=[int(x) for x in re.findall(r"[1-6]",str(t or ""))]
    return tuple(xs[:3]) if len(xs)>=3 and len(set(xs[:3]))==3 else None
def score(entries,ticket):
    ls=lanes(ticket)
    by={si(e.get("lane")):e for e in entries}
    if ls is None or set(by)!={1,2,3,4,5,6}:return None
    vals=[]
    for lane in range(1,7):
        x=sf(by[lane].get("motor_place2_rate"))
        if x is None or not 0<=x<=100:return None
        vals.append(x)
    mu=sum(vals)/6
    sd=math.sqrt(sum((x-mu)**2 for x in vals)/6)
    if sd<1e-12:return None
    z={i+1:(vals[i]-mu)/sd for i in range(6)}
    a,b,c=ls
    return W[0]*z[a]+W[1]*z[b]+W[2]*z[c]
def summ(rows):
    rr=[r for r in rows if r.get("hit") is not None and r.get("return_yen") is not None]
    inv=len(rr)*100
    gross=sum(si(r.get("return_yen")) if bool(r.get("hit")) else 0 for r in rr)
    hits=sum(int(bool(r.get("hit"))) for r in rr)
    vals=sorted([si(r.get("return_yen")) for r in rr if bool(r.get("hit"))],reverse=True)
    return {"evaluated":len(rr),"hits":hits,"investment_yen":inv,"return_yen":gross,
            "profit_yen":gross-inv,"roi_pct":round(gross/inv*100,4) if inv else None,
            "largest_hit_yen":vals[0] if vals else 0,
            "largest_hit_share_pct":round(vals[0]/gross*100,4) if vals and gross else 0.0}

def main():
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:raise RuntimeError("DATABASE_URL required")
    print("S03_RECON_POLICY=FIXED_RULE_READ_ONLY_TIMING_RECONCILIATION",flush=True)
    print("S03_RECON_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0",flush=True)
    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("""select s.race_id,s.race_date,s.ticket,s.snapshot_at,s.hit,s.return_yen,
                                  r.deadline_at
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
    pos=[]; valid=[]; late=[]; missing=0
    for r in rows:
        s=score(ent.get(str(r["race_id"]),[]),r.get("ticket"))
        if s is None:
            missing+=1; continue
        if s<=0:continue
        x=dict(r);x["motor2_score"]=s;pos.append(x)
        snap=jt(r.get("snapshot_at"));deadline=jt(r.get("deadline_at"))
        if snap is not None and deadline is not None and snap<deadline:valid.append(x)
        else:late.append(x)
    out={"period":{"start":START.isoformat(),"end":END.isoformat()},"source_s03_rows":len(rows),
         "missing_motor_rows":missing,"m2_positive_all":summ(pos),
         "m2_positive_timing_valid":summ(valid),"m2_positive_late_or_unknown":summ(late),
         "counts":{"positive_all":len(pos),"positive_timing_valid":len(valid),"positive_late_or_unknown":len(late)},
         "safety":{"db_write":False,"line":False,"buy":False,"production_change":False}}
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("S03_RECON_RESULT_JSON="+json.dumps(out,sort_keys=True),flush=True)
    print("S03_RECON_RESULT=PASS_READ_ONLY",flush=True)
if __name__=="__main__":main()
