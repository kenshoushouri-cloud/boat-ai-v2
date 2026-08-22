# -*- coding: utf-8 -*-
"""Read-only diagnostic for model-vs-market disagreement after de-vig normalization.

Uses v24 odds-independent 120-ticket probabilities at TEMP=1.20 and compares
against q=(1/odds)/sum(1/odds) within each complete 120-ticket race.
No DB writes, no Production/Shadow/LINE changes.
"""
from __future__ import annotations
import math, os, re
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
import psycopg
from psycopg.rows import dict_row
import v24_pre_candidate_notifier_pg as v24

DB=os.getenv('DATABASE_URL','').strip(); START=date(2026,1,1); END=date(2026,8,22); TEMP=1.20
BINS=[(0,.5,'LT0.5'),(.5,.8,'0.5-0.8'),(.8,1.0,'0.8-1.0'),(1.0,1.25,'1.0-1.25'),(1.25,1.5,'1.25-1.5'),(1.5,2.0,'1.5-2.0'),(2.0,3.0,'2.0-3.0'),(3.0,float('inf'),'GE3.0')]

def nt(v):
 x=re.findall(r'[1-6]',str(v or '')); return '-'.join(x[:3]) if len(x)>=3 else str(v or '').strip()
def nextm(d): return date(d.year+1,1,1) if d.month==12 else date(d.year,d.month+1,1)
def bname(x):
 for a,b,n in BINS:
  if a<=x<b:return n
 return None
def acc(): return {'n':0,'h':0,'ret':0,'races':set(),'ratio':0.0}
def add(a,rid,ratio,hit,pay):
 a['n']+=1;a['h']+=int(hit);a['ret']+=int(pay) if hit else 0;a['races'].add(rid);a['ratio']+=ratio
def fmt(a):
 n=a['n'];return f"n:{n} races:{len(a['races'])} hits:{a['h']} hit:{(100*a['h']/n if n else 0):.3f}% ROI:{(a['ret']/n if n else 0):.1f}% mean_ratio:{(a['ratio']/n if n else 0):.3f}"
def probs(entries,venue,temp):
 by=v24._entry_by_lane(entries); raw={i:v24._lane_raw_strength(by[i],i,venue) for i in range(1,7)}
 w={i:math.exp(raw[i]/temp) for i in range(1,7)}; tot=sum(w.values()); out={}
 for a in range(1,7):
  pa=w[a]/tot; tb=tot-w[a]
  for b in range(1,7):
   if b==a: continue
   pb=w[b]/tb; tc=tb-w[b]
   for c in range(1,7):
    if c in (a,b): continue
    out[f'{a}-{b}-{c}']=pa*pb*(w[c]/tc)
 return out

def main():
 if not DB: raise RuntimeError('DATABASE_URL is required')
 print(f'BAO_NORM_MODE=read_only temp:{TEMP:.2f} period:{START}..{END}',flush=True)
 bins={n:acc() for _,_,n in BINS}; months={}; over=[]; model_ll=[]; market_ll=[]; model_br=[]; market_br=[]; mranks=[]; qranks=[]; race_n=0
 cur=date(START.year,START.month,1)
 with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
  while cur<=END:
   mx=nextm(cur); a=max(cur,START); z=min(mx,END+timedelta(days=1)); key=a.strftime('%Y-%m'); mb={n:acc() for _,_,n in BINS}; m_races=0
   with conn.cursor() as c:
    c.execute("set statement_timeout='120s'")
    c.execute("select r.race_id,coalesce(r.venue_id,r.venue_code) venue_id from v2_races r where r.race_date >= %s and r.race_date < %s order by r.race_id",(a,z)); races=[dict(x) for x in c.fetchall()]
    c.execute("select e.race_id,e.lane,e.racer_number,e.racer_class,e.racer_name,e.national_win_rate,e.national_place2_rate,e.local_win_rate,e.local_place2_rate,e.avg_st,e.motor_no,e.boat_no from v2_race_entries e join v2_races r on r.race_id=e.race_id where r.race_date >= %s and r.race_date < %s order by e.race_id,e.lane",(a,z)); ents=[dict(x) for x in c.fetchall()]
   eb=defaultdict(list)
   for e in ents: eb[str(e['race_id'])].append(e)
   pred={}
   for r in races:
    rid=str(r['race_id']); es=eb.get(rid,[])
    if len(es)!=6: continue
    try:p=probs(es,str(r.get('venue_id') or '').zfill(2),TEMP)
    except Exception:continue
    if len(p)==120 and abs(sum(p.values())-1)<1e-9:pred[rid]=p
   with conn.cursor() as c:
    c.execute("select o.race_id,o.ticket,o.odds from v2_odds_trifecta o join v2_races r on r.race_id=o.race_id where r.race_date >= %s and r.race_date < %s and o.odds>1 order by o.race_id,o.ticket",(a,z)); oo=[dict(x) for x in c.fetchall()]
    c.execute("select res.race_id,res.trifecta_ticket,coalesce(res.trifecta_payout_yen,res.trifecta_payout,0) payout from v2_results res join v2_races r on r.race_id=res.race_id where r.race_date >= %s and r.race_date < %s",(a,z)); rr={str(x['race_id']):(nt(x['trifecta_ticket']),int(float(x['payout'] or 0))) for x in c.fetchall()}
   ob=defaultdict(dict)
   for x in oo: ob[str(x['race_id'])][nt(x['ticket'])]=float(x['odds'])
   for rid,p in pred.items():
    od=ob.get(rid,{}); res=rr.get(rid)
    if len(od)!=120 or len(p)!=120 or not res or any(t not in od for t in p): continue
    inv={t:1.0/od[t] for t in p}; s=sum(inv.values())
    if not math.isfinite(s) or s<=0: continue
    q={t:inv[t]/s for t in p}; actual,pay=res
    if actual not in p: continue
    race_n+=1;m_races+=1;over.append(s)
    pa=max(p[actual],1e-12); qa=max(q[actual],1e-12)
    model_ll.append(-math.log(pa)); market_ll.append(-math.log(qa))
    model_br.append(sum((p[t]-(1.0 if t==actual else 0.0))**2 for t in p))
    market_br.append(sum((q[t]-(1.0 if t==actual else 0.0))**2 for t in p))
    pr={t:i for i,(t,_) in enumerate(sorted(p.items(),key=lambda kv:(-kv[1],kv[0])),1)}
    qr={t:i for i,(t,_) in enumerate(sorted(q.items(),key=lambda kv:(-kv[1],kv[0])),1)}
    mranks.append(pr[actual]);qranks.append(qr[actual])
    for t in p:
     ratio=p[t]/max(q[t],1e-12); bn=bname(ratio)
     if not bn: continue
     hit=t==actual; add(bins[bn],rid,ratio,hit,pay);add(mb[bn],rid,ratio,hit,pay)
   months[key]=m_races
   print(f'BAO_NORM_MONTH={key} complete_races:{m_races}',flush=True)
   for _,_,n in BINS:
    if mb[n]['n']: print(f'BAO_NORM_MONTH_BIN={key} ratio:{n} '+fmt(mb[n]),flush=True)
   cur=mx
 print(f'BAO_NORM_RACES={race_n}',flush=True)
 print(f'BAO_NORM_OVERROUND=mean:{mean(over):.4f} min:{min(over):.4f} max:{max(over):.4f}',flush=True)
 print(f'BAO_NORM_MODEL_SCORE=logloss:{mean(model_ll):.6f} brier:{mean(model_br):.6f} mean_actual_rank:{mean(mranks):.2f}',flush=True)
 print(f'BAO_NORM_MARKET_SCORE=logloss:{mean(market_ll):.6f} brier:{mean(market_br):.6f} mean_actual_rank:{mean(qranks):.2f}',flush=True)
 print(f'BAO_NORM_SCORE_DELTA=model_minus_market logloss:{mean(model_ll)-mean(market_ll):.6f} brier:{mean(model_br)-mean(market_br):.6f} rank:{mean(mranks)-mean(qranks):.2f}',flush=True)
 for _,_,n in BINS:
  if bins[n]['n']: print(f'BAO_NORM_ALL_BIN=ratio:{n} '+fmt(bins[n]),flush=True)
 print('BAO_NORM_POLICY=diagnostic_only_no_production_value_rule',flush=True)
 print('BAO_NORM_NEXT=train_only_model_market_blend_or_residual_calibration_if_market_dominates',flush=True)
 print('BAO_NORM_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__':main()
