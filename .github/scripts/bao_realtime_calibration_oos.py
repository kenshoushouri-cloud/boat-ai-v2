# -*- coding: utf-8 -*-
"""Read-only multi-source OOS audit for a Bao-style value layer.

Scans existing model+market tables, chooses the largest source that can be
joined to results, then evaluates chronological probability calibration and
model-vs-market edge. No DB writes or Production/Shadow/LINE changes.
"""
from __future__ import annotations
import os,re
from collections import defaultdict
from datetime import date
from statistics import mean
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip()
SOURCES=[
 'v2_realtime_decisions','v2_candidate_filter_shadow','v2_n02_windlt4_final_shadow',
 'v2_previous_st_shadow_rankings','v2_racer_course_shadow_rankings',
 'v2_realtime_condition_shadow_rankings','v2_v24_motor2_forward_shadow',
]
PROB_NAMES=['probability','prob','shadow_prob','motor2_prob','baseline_prob','base_prob']
TS_NAMES=['decision_at','created_at','updated_at','snapshot_at','saved_at','evaluated_at','collected_at']

def sf(v,d=None):
 try:return float(v) if v is not None and v!='' else d
 except:return d
def qi(s):return '"'+s.replace('"','""')+'"'
def cols(c,t):
 with c.cursor() as x:
  x.execute("select column_name from information_schema.columns where table_schema='public' and table_name=%s order by ordinal_position",(t,));return [str(r['column_name']) for r in x.fetchall()]
def choose(cs,names):return next((n for n in names if n in cs),None)
def nt(v):
 nums=re.findall(r'[1-6]',str(v or ''));return '-'.join(nums[:3]) if len(nums)>=3 else str(v or '').strip()
def pb(p):
 return 'LT0.5%' if p<.005 else '0.5-1%' if p<.01 else '1-2%' if p<.02 else '2-3%' if p<.03 else '3-5%' if p<.05 else '5-8%' if p<.08 else '8-12%' if p<.12 else 'GE12%'
def eb(e):
 return 'LT0.6' if e<.6 else '0.6-0.8' if e<.8 else '0.8-1.0' if e<1 else '1.0-1.1' if e<1.1 else '1.1-1.25' if e<1.25 else '1.25-1.5' if e<1.5 else '1.5-2.0' if e<2 else 'GE2.0'
def met(xs,key='prob'):
 n=len(xs)
 if not n:return dict(n=0,h=0,hit=0.,roi=0.,br=0.,mp=0.,me=0.)
 h=sum(x['hit'] for x in xs);ret=sum(x['payout'] for x in xs if x['hit'])
 return dict(n=n,h=h,hit=h/n*100,roi=ret/(n*100)*100,br=mean((x[key]-x['hit'])**2 for x in xs),mp=mean(x[key] for x in xs),me=mean(x['edge'] for x in xs))
def fm(m):return f"n:{m['n']} hits:{m['h']} hit:{m['hit']:.2f}% ROI:{m['roi']:.1f}% brier:{m['br']:.6f} mean_prob:{m['mp']:.5f} mean_edge:{m['me']:.3f}"
def splitdays(ds):
 z=[];n=len(ds)
 for f in (.5,.67,.8):
  k=max(1,min(n-1,int(n*f)))
  if k>=3 and n-k>=2:z.append((ds[k-1],ds[k],ds[-1]))
 return list(dict.fromkeys(z))

def main():
 if not DB:raise RuntimeError('DATABASE_URL is required')
 print('BAO_MS_MODE=read_only',flush=True);print('BAO_MS_PRINCIPLE=model_probability_separate_from_market_price',flush=True)
 with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as c:
  rc=cols(c,'v2_results');pay=choose(rc,['trifecta_payout_yen','trifecta_payout']);rt=choose(rc,['trifecta_ticket'])
  if not pay or not rt:raise SystemExit('result columns missing')
  candidates=[]
  for t in SOURCES:
   cs=cols(c,t)
   if not cs:continue
   p=choose(cs,PROB_NAMES);o=choose(cs,['odds']);ticket=choose(cs,['ticket']);rid=choose(cs,['race_id']);ts=choose(cs,TS_NAMES)
   if not all([p,o,ticket,rid]):
    print(f'BAO_MS_SOURCE={t} state:skip prob:{p} odds:{o} ticket:{ticket} race:{rid}',flush=True);continue
   q=f"""select count(*) n,count(distinct d.{qi(rid)}) races,min(d.{qi(rid)}::text) minrid,max(d.{qi(rid)}::text) maxrid,
   min(d.{qi(p)}::float8) pmin,max(d.{qi(p)}::float8) pmax,avg(d.{qi(p)}::float8) pavg
   from {qi(t)} d join v2_results r on r.race_id=d.{qi(rid)}
   where d.{qi(p)} is not null and d.{qi(o)} is not null and d.{qi(p)}::float8>0 and d.{qi(o)}::float8>1"""
   try:
    with c.cursor() as x:x.execute("set statement_timeout='60s'");x.execute(q);s=dict(x.fetchone())
   except Exception as e:
    print(f'BAO_MS_SOURCE={t} state:error type:{type(e).__name__}',flush=True);continue
   n=int(s['n'] or 0);races=int(s['races'] or 0)
   print(f"BAO_MS_SOURCE={t} n:{n} races:{races} pcol:{p} ts:{ts} period:{s['minrid']}..{s['maxrid']} pmin:{s['pmin']} pmax:{s['pmax']} pavg:{s['pavg']}",flush=True)
   if n:candidates.append((n,t,p,o,ticket,rid,ts))
  if not candidates:raise SystemExit('no usable model-market source')
  _,t,p,o,ticket,rid,ts=max(candidates,key=lambda x:x[0])
  print(f'BAO_MS_SELECTED={t} prob:{p} odds:{o} ts:{ts}',flush=True)
  order=f"order by d.{qi(rid)},d.{qi(ticket)},d.{qi(ts)} desc nulls last" if ts else f"order by d.{qi(rid)},d.{qi(ticket)}"
  q=f"""select distinct on(d.{qi(rid)},d.{qi(ticket)}) d.{qi(rid)}::text race_id,d.{qi(ticket)}::text ticket,d.{qi(p)}::float8 prob_raw,d.{qi(o)}::float8 odds,
  r.{qi(rt)}::text result_ticket,coalesce(r.{qi(pay)},0)::float8 payout
  from {qi(t)} d join v2_results r on r.race_id=d.{qi(rid)}
  where d.{qi(p)} is not null and d.{qi(o)} is not null and d.{qi(p)}::float8>0 and d.{qi(o)}::float8>1 and d.{qi(rid)}::text~'^[0-9]{{8}}' {order}"""
  with c.cursor() as x:x.execute("set statement_timeout='120s'");x.execute(q);raw=[dict(r) for r in x.fetchall()]
 vals=[sf(r['prob_raw']) for r in raw if sf(r['prob_raw']) is not None];pct=bool(vals and (max(vals)>1 or mean(vals)>.2))
 print(f"BAO_MS_PROB_SCALE={'percent_0_100' if pct else 'fraction_0_1'}",flush=True)
 rows=[]
 for r in raw:
  rv=str(r['race_id']);ds=f'{rv[:4]}-{rv[4:6]}-{rv[6:8]}'
  try:date.fromisoformat(ds)
  except:continue
  p0=sf(r['prob_raw']);od=sf(r['odds']);po=sf(r['payout'],0) or 0
  if p0 is None or od is None:continue
  if pct:p0/=100
  if not(0<p0<1):continue
  rows.append(dict(date=ds,race_id=rv,prob=p0,odds=od,edge=p0*od,hit=int(nt(r['ticket'])==nt(r['result_ticket'])),payout=int(round(po))))
 days=sorted({x['date'] for x in rows});races=len({x['race_id'] for x in rows})
 print(f'BAO_MS_ROWS={len(rows)} races:{races} days:{len(days)}',flush=True)
 if days:print(f'BAO_MS_PERIOD={days[0]}..{days[-1]}',flush=True)
 if len(rows)<100:raise SystemExit('selected source insufficient after normalization')
 print('BAO_MS_ALL='+fm(met(rows)),flush=True)
 bp,be=defaultdict(list),defaultdict(list)
 for x in rows:bp[pb(x['prob'])].append(x);be[eb(x['edge'])].append(x)
 for k in ['LT0.5%','0.5-1%','1-2%','2-3%','3-5%','5-8%','8-12%','GE12%']:
  if bp[k]:print(f'BAO_MS_PROB_BIN={k} '+fm(met(bp[k])),flush=True)
 for k in ['LT0.6','0.6-0.8','0.8-1.0','1.0-1.1','1.1-1.25','1.25-1.5','1.5-2.0','GE2.0']:
  if be[k]:print(f'BAO_MS_EDGE_BIN={k} '+fm(met(be[k])),flush=True)
 ss=splitdays(days);print(f'BAO_MS_SPLITS={len(ss)}',flush=True)
 for i,(te,ts,tx) in enumerate(ss,1):
  tr=[x for x in rows if x['date']<=te];test=[x.copy() for x in rows if ts<=x['date']<=tx]
  sp=sum(x['prob'] for x in tr);h=sum(x['hit'] for x in tr);scale=max(.25,min(4.,h/sp if sp else 1.))
  for x in test:x['cal_prob']=max(1e-6,min(.999999,x['prob']*scale));x['cal_edge']=x['cal_prob']*x['odds']
  print(f'BAO_MS_SPLIT={i} train_end:{te} test:{ts}..{tx} train_n:{len(tr)} test_n:{len(test)} scale:{scale:.4f}',flush=True)
  print(f'BAO_MS_SPLIT_RAW={i} '+fm(met(test,'prob')),flush=True);print(f'BAO_MS_SPLIT_CAL={i} '+fm(met(test,'cal_prob')),flush=True)
  for th in (.8,1.,1.1,1.25,1.5):
   xs=[x for x in test if x['cal_edge']>=th]
   if xs:print(f'BAO_MS_SPLIT_EDGE={i} threshold:{th:.2f} '+fm(met(xs,'cal_prob')),flush=True)
 ready=len(rows)>=500 and len(days)>=6 and len(ss)>=2
 print(f"BAO_MS_OOS_READINESS={'READY' if ready else 'LIMITED'}",flush=True)
 print('BAO_MS_NEXT=full_market_120_ticket_probability_model_and_closing_odds_alignment',flush=True)
 print('BAO_MS_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__':main()
