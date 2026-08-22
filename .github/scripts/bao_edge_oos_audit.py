# -*- coding: utf-8 -*-
"""Read-only OOS audit for a Bao-inspired model-vs-market edge layer.

Scope is existing forward/shadow candidate rows only. This does not claim full
120-ticket probability calibration. It asks whether, inside the already-created
candidate universe, higher model-implied value (prob * odds) is associated with
better realized ROI and whether the model probability is directionally calibrated.

No writes. No Production/Shadow/LINE changes.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime
import math
import psycopg
from psycopg.rows import dict_row

DB=os.environ.get('DATABASE_URL','').strip()
TABLE='v2_candidate_filter_shadow'

EDGE_BINS=[(0.0,0.8,'LT0.8'),(0.8,1.0,'0.8-1.0'),(1.0,1.1,'1.0-1.1'),(1.1,1.25,'1.1-1.25'),(1.25,1.5,'1.25-1.5'),(1.5,2.0,'1.5-2.0'),(2.0,999.0,'GE2.0')]
PROB_BINS=[(0,.01,'LT1%'),(.01,.02,'1-2%'),(.02,.03,'2-3%'),(.03,.05,'3-5%'),(.05,.08,'5-8%'),(.08,.12,'8-12%'),(.12,1.01,'GE12%')]


def f(v,d=None):
    try:return float(v)
    except Exception:return d

def norm_ticket(v):
    if v is None:return ''
    s=str(v).replace(' ','').replace('−','-').replace('ー','-')
    ds=[c for c in s if c in '123456']
    return '-'.join(ds[:3]) if len(ds)>=3 else s

def race_date(rid):
    s=''.join(c for c in str(rid or '')[:8] if c.isdigit())
    if len(s)!=8:return None
    try:return datetime.strptime(s,'%Y%m%d').date()
    except Exception:return None

def bucket(v,bins):
    for lo,hi,name in bins:
        if lo<=v<hi:return name
    return 'OTHER'
def metrics(xs):
    n=len(xs)
    if not n:return {'n':0}
    hits=sum(x['hit'] for x in xs)
    ret=sum(x['return_yen'] for x in xs)
    inv=n*100
    brier=sum((x['prob']-x['hit'])**2 for x in xs)/n
    return {'n':n,'hits':hits,'hit_pct':100*hits/n,'roi':100*ret/inv if inv else 0,'brier':brier,'mean_prob':sum(x['prob'] for x in xs)/n,'mean_edge':sum(x['edge'] for x in xs)/n}
def emit(prefix,m):
    if not m or not m.get('n'):
        print(prefix+' n:0',flush=True); return
    print(prefix+f" n:{m['n']} hits:{m['hits']} hit:{m['hit_pct']:.2f}% ROI:{m['roi']:.1f}% brier:{m['brier']:.5f} mean_prob:{m['mean_prob']:.5f} mean_edge:{m['mean_edge']:.3f}",flush=True)

def main():
    if not DB:raise RuntimeError('DATABASE_URL required')
    print('BAO_EDGE_MODE=read_only',flush=True)
    print('BAO_EDGE_SCOPE=existing_candidate_shadow_only',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute('set max_parallel_workers_per_gather=0')
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute("""
              select race_id,ticket,odds,prob,raw_ev,result_ticket,payout_yen,evaluated_at
              from v2_candidate_filter_shadow
              where prob is not null and odds is not null and odds>0
                and result_ticket is not null and payout_yen is not null
              order by race_id,ticket
            """)
            raw=[dict(r) for r in cur.fetchall()]
    xs=[]
    ev_diffs=[]
    for r in raw:
        p=f(r.get('prob')); o=f(r.get('odds')); pay=f(r.get('payout_yen'),0) or 0
        d=race_date(r.get('race_id'))
        if p is None or o is None or d is None or not (0<=p<=1) or o<=0:continue
        hit=int(norm_ticket(r.get('ticket'))==norm_ticket(r.get('result_ticket')))
        edge=p*o
        rv=f(r.get('raw_ev'))
        if rv is not None:ev_diffs.append(abs(rv-edge))
        xs.append({'date':d,'month':d.strftime('%Y-%m'),'prob':p,'odds':o,'edge':edge,'hit':hit,'return_yen':pay if hit else 0})
    print(f'BAO_EDGE_ROWS={len(xs)} raw_rows:{len(raw)}',flush=True)
    if not xs:raise RuntimeError('no evaluable candidate rows')
    if ev_diffs:
        print(f'BAO_EDGE_RAW_EV_CHECK=n:{len(ev_diffs)} mean_abs_diff:{sum(ev_diffs)/len(ev_diffs):.6f} max_abs_diff:{max(ev_diffs):.6f}',flush=True)
    emit('BAO_EDGE_ALL',metrics(xs))
    # Probability calibration: observed hit rate should broadly rise with predicted probability.
    for _,_,name in PROB_BINS:
        part=[x for x in xs if bucket(x['prob'],PROB_BINS)==name]
        emit(f'BAO_EDGE_PROB_BIN={name}',metrics(part))
    # Economic value buckets.
    for _,_,name in EDGE_BINS:
        part=[x for x in xs if bucket(x['edge'],EDGE_BINS)==name]
        emit(f'BAO_EDGE_VALUE_BIN={name}',metrics(part))
    # Month-by-month forward robustness for edge >=1 and >=1.25.
    months=sorted({x['month'] for x in xs})
    print(f"BAO_EDGE_MONTHS={','.join(months)}",flush=True)
    for mo in months:
        mrows=[x for x in xs if x['month']==mo]
        emit(f'BAO_EDGE_MONTH={mo} ALL',metrics(mrows))
        emit(f'BAO_EDGE_MONTH={mo} EDGE_GE1',metrics([x for x in mrows if x['edge']>=1.0]))
        emit(f'BAO_EDGE_MONTH={mo} EDGE_GE1.25',metrics([x for x in mrows if x['edge']>=1.25]))
    # Directional gates, not a Production decision.
    hi=metrics([x for x in xs if x['edge']>=1.25])
    low=metrics([x for x in xs if x['edge']<1.0])
    print(f"BAO_EDGE_DIAGNOSTIC=high_n:{hi.get('n',0)} high_roi:{hi.get('roi',0):.1f} low_n:{low.get('n',0)} low_roi:{low.get('roi',0):.1f}",flush=True)
    print('BAO_EDGE_RESULT=PASS_READ_ONLY',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(f"BAO_EDGE_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}",flush=True)
        raise
