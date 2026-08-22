# -*- coding: utf-8 -*-
"""Read-only OOS audit for a Bao-style model-vs-market value layer.

No DB writes, no Production/Shadow/LINE changes.
"""
from __future__ import annotations
import os, re
from collections import defaultdict
from datetime import date
from statistics import mean
import psycopg
from psycopg.rows import dict_row

DATABASE_URL=os.getenv("DATABASE_URL","").strip()

def sf(v,d=None):
    try:return float(v) if v is not None and v!="" else d
    except Exception:return d

def qi(s): return '"'+s.replace('"','""')+'"'
def cols(conn,t):
    with conn.cursor() as c:
        c.execute("select column_name from information_schema.columns where table_schema='public' and table_name=%s order by ordinal_position",(t,))
        return [str(x['column_name']) for x in c.fetchall()]
def choose(cs,names):
    return next((x for x in names if x in cs),None)
def nticket(v):
    if v is None:return ""
    nums=re.findall(r"[1-6]",str(v))
    return "-".join(nums[:3]) if len(nums)>=3 else str(v).strip()
def pbin(p):
    if p<.005:return "LT0.5%"
    if p<.01:return "0.5-1%"
    if p<.02:return "1-2%"
    if p<.03:return "2-3%"
    if p<.05:return "3-5%"
    if p<.08:return "5-8%"
    if p<.12:return "8-12%"
    return "GE12%"
def ebin(e):
    if e<.6:return "LT0.6"
    if e<.8:return "0.6-0.8"
    if e<1:return "0.8-1.0"
    if e<1.1:return "1.0-1.1"
    if e<1.25:return "1.1-1.25"
    if e<1.5:return "1.25-1.5"
    if e<2:return "1.5-2.0"
    return "GE2.0"
def metrics(xs,key="prob"):
    n=len(xs)
    if not n:return dict(n=0,hits=0,hit=0.,roi=0.,brier=0.,mp=0.,me=0.)
    h=sum(x['hit'] for x in xs); ret=sum(x['payout'] for x in xs if x['hit'])
    return dict(n=n,hits=h,hit=h/n*100,roi=ret/(n*100)*100,
                brier=mean((x[key]-x['hit'])**2 for x in xs),mp=mean(x[key] for x in xs),me=mean(x['edge'] for x in xs))
def fmt(m):
    return f"n:{m['n']} hits:{m['hits']} hit:{m['hit']:.2f}% ROI:{m['roi']:.1f}% brier:{m['brier']:.6f} mean_prob:{m['mp']:.5f} mean_edge:{m['me']:.3f}"
def splits(days):
    out=[]; n=len(days)
    for f in (.50,.67,.80):
        k=max(1,min(n-1,int(n*f)))
        if k>=3 and n-k>=2:out.append((days[k-1],days[k],days[-1]))
    seen=set(); z=[]
    for x in out:
        if x not in seen:seen.add(x);z.append(x)
    return z

def main():
    if not DATABASE_URL:raise RuntimeError("DATABASE_URL is required")
    print("BAO_RT_MODE=read_only",flush=True)
    print("BAO_RT_PRINCIPLE=probability_separate_from_market_odds",flush=True)
    with psycopg.connect(DATABASE_URL,row_factory=dict_row,autocommit=True) as conn:
        dc,rc=cols(conn,'v2_realtime_decisions'),cols(conn,'v2_results')
        pcol=choose(dc,['probability','prob']); ocol=choose(dc,['odds']); tcol=choose(dc,['ticket']); rid=choose(dc,['race_id'])
        ts=choose(dc,['decision_at','created_at','updated_at','snapshot_at','saved_at','evaluated_at'])
        pay=choose(rc,['trifecta_payout_yen','trifecta_payout']); rt=choose(rc,['trifecta_ticket'])
        print(f"BAO_RT_SCHEMA=prob:{pcol} odds:{ocol} ticket:{tcol} race:{rid} ts:{ts} payout:{pay}",flush=True)
        if not all([pcol,ocol,tcol,rid,pay,rt]):raise SystemExit('required columns missing')
        with conn.cursor() as c:
            c.execute(f"select count(*) n,count(*) filter(where {qi(pcol)} is not null) pn,min({qi(pcol)}::float8) pmin,max({qi(pcol)}::float8) pmax,avg({qi(pcol)}::float8) pavg from v2_realtime_decisions")
            st=dict(c.fetchone())
        print(f"BAO_RT_RAW_TABLE=rows:{st['n']} prob_rows:{st['pn']} pmin:{st['pmin']} pmax:{st['pmax']} pavg:{st['pavg']}",flush=True)
        order=f"order by d.{qi(rid)},d.{qi(tcol)},d.{qi(ts)} desc nulls last" if ts else f"order by d.{qi(rid)},d.{qi(tcol)}"
        sql=f"""select distinct on(d.{qi(rid)},d.{qi(tcol)}) d.{qi(rid)}::text race_id,d.{qi(tcol)}::text ticket,
        d.{qi(pcol)}::float8 prob_raw,d.{qi(ocol)}::float8 odds,r.{qi(rt)}::text result_ticket,coalesce(r.{qi(pay)},0)::float8 payout
        from v2_realtime_decisions d join v2_results r on r.race_id=d.{qi(rid)}
        where d.{qi(pcol)} is not null and d.{qi(ocol)} is not null and d.{qi(pcol)}::float8>0 and d.{qi(pcol)}::float8<=100
        and d.{qi(ocol)}::float8>1 and d.{qi(rid)}::text~'^[0-9]{{8}}' {order}"""
        with conn.cursor() as c:
            c.execute("set statement_timeout='120s'"); c.execute(sql); raw=[dict(x) for x in c.fetchall()]
    vals=[sf(x['prob_raw']) for x in raw if sf(x['prob_raw']) is not None]
    percent_mode=bool(vals and (max(vals)>1.0 or mean(vals)>0.20))
    print(f"BAO_RT_PROB_SCALE={'percent_0_100' if percent_mode else 'fraction_0_1'}",flush=True)
    rows=[]
    for r in raw:
        ridv=str(r['race_id']); ds=f"{ridv[:4]}-{ridv[4:6]}-{ridv[6:8]}"
        try:date.fromisoformat(ds)
        except Exception:continue
        p=sf(r['prob_raw']); o=sf(r['odds']); payout=sf(r['payout'],0) or 0
        if p is None or o is None:continue
        if percent_mode:p/=100.0
        if not(0<p<1):continue
        hit=int(nticket(r['ticket'])==nticket(r['result_ticket']))
        rows.append(dict(date=ds,race_id=ridv,ticket=nticket(r['ticket']),prob=p,odds=o,edge=p*o,hit=hit,payout=int(round(payout))))
    days=sorted({x['date'] for x in rows}); races=len({x['race_id'] for x in rows})
    print(f"BAO_RT_ROWS={len(rows)} races:{races} days:{len(days)}",flush=True)
    if days:print(f"BAO_RT_PERIOD={days[0]}..{days[-1]}",flush=True)
    if len(rows)<100:print("BAO_RT_RESULT=INSUFFICIENT_ROWS",flush=True);raise SystemExit(2)
    print("BAO_RT_ALL="+fmt(metrics(rows)),flush=True)
    bp,be=defaultdict(list),defaultdict(list)
    for x in rows:bp[pbin(x['prob'])].append(x);be[ebin(x['edge'])].append(x)
    for k in ['LT0.5%','0.5-1%','1-2%','2-3%','3-5%','5-8%','8-12%','GE12%']:
        if bp[k]:print(f"BAO_RT_PROB_BIN={k} "+fmt(metrics(bp[k])),flush=True)
    for k in ['LT0.6','0.6-0.8','0.8-1.0','1.0-1.1','1.1-1.25','1.25-1.5','1.5-2.0','GE2.0']:
        if be[k]:print(f"BAO_RT_EDGE_BIN={k} "+fmt(metrics(be[k])),flush=True)
    ss=splits(days);print(f"BAO_RT_SPLITS={len(ss)}",flush=True)
    for i,(te,ts,tx) in enumerate(ss,1):
        tr=[x for x in rows if x['date']<=te]; test=[x.copy() for x in rows if ts<=x['date']<=tx]
        sp=sum(x['prob'] for x in tr); h=sum(x['hit'] for x in tr); scale=max(.25,min(4.0,h/sp if sp else 1.0))
        for x in test:x['cal_prob']=max(1e-6,min(.999999,x['prob']*scale));x['cal_edge']=x['cal_prob']*x['odds']
        print(f"BAO_RT_SPLIT={i} train_end:{te} test:{ts}..{tx} train_n:{len(tr)} test_n:{len(test)} scale:{scale:.4f}",flush=True)
        print(f"BAO_RT_SPLIT_RAW={i} "+fmt(metrics(test,'prob')),flush=True)
        print(f"BAO_RT_SPLIT_CAL={i} "+fmt(metrics(test,'cal_prob')),flush=True)
        for th in (.8,1.0,1.1,1.25,1.5):
            xs=[x for x in test if x['cal_edge']>=th]
            if xs:print(f"BAO_RT_SPLIT_EDGE={i} threshold:{th:.2f} "+fmt(metrics(xs,'cal_prob')),flush=True)
    enough=len(days)>=6 and len(rows)>=500 and len(ss)>=2
    print(f"BAO_RT_OOS_READINESS={'READY' if enough else 'LIMITED'}",flush=True)
    print("BAO_RT_NEXT=full_market_probability_calibration_before_any_production_value_rule",flush=True)
    print("BAO_RT_RESULT=PASS_READ_ONLY",flush=True)
if __name__=='__main__':main()
