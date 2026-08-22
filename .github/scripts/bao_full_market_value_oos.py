# -*- coding: utf-8 -*-
"""Full-market historical value audit using an odds-independent calibrated model.

Calibration provenance:
- PROB_TEMP=1.20 was selected using races through 2025-12 only in the prior
  expanding-OOS audit and then repeatedly reproduced on later train windows.

This audit evaluates only 2026-01-01..2026-08-22. For each month it:
1. fetches races + entries and computes all 120 probabilities with temp 1.20;
2. only then fetches historical market odds;
3. joins results for realized 100-yen return and aggregates edge buckets.

No ticket probabilities or outputs are persisted. No DB writes.
Historical v2_odds_trifecta has no guaranteed actionable timestamp here, so
results are research evidence only; any Production threshold requires realtime
odds forward validation.
"""
from __future__ import annotations
import math, os, re
from collections import defaultdict
from datetime import date, timedelta
import psycopg
from psycopg.rows import dict_row
import v24_pre_candidate_notifier_pg as v24

DB=os.getenv('DATABASE_URL','').strip()
START=date.fromisoformat('2026-01-01');END=date.fromisoformat('2026-08-22');TEMP=1.20
BINS=[(0,.5,'LT0.5'),(.5,.7,'0.5-0.7'),(.7,.85,'0.7-0.85'),(.85,1.0,'0.85-1.0'),(1.0,1.1,'1.0-1.1'),(1.1,1.25,'1.1-1.25'),(1.25,1.5,'1.25-1.5'),(1.5,2.0,'1.5-2.0'),(2.0,float('inf'),'GE2.0')]
THRESH=[.8,1.0,1.1,1.25,1.5,2.0]

def nt(v):
 x=re.findall(r'[1-6]',str(v or ''));return '-'.join(x[:3]) if len(x)>=3 else str(v or '').strip()
def nextm(d):return date(d.year+1,1,1) if d.month==12 else date(d.year,d.month+1,1)
def edge_bin(e):
 for a,b,n in BINS:
  if a<=e<b:return n
 return 'OTHER'
def acc():return {'n':0,'hits':0,'ret':0,'sum_edge':0.,'races':set()}
def add(a,rid,edge,hit,payout):
 a['n']+=1;a['hits']+=int(hit);a['ret']+=int(payout) if hit else 0;a['sum_edge']+=edge;a['races'].add(rid)
def fm(a):
 n=a['n'];return f"n:{n} races:{len(a['races'])} hits:{a['hits']} hit:{(a['hits']/n*100 if n else 0):.3f}% ROI:{(a['ret']/(n*100)*100 if n else 0):.1f}% mean_edge:{(a['sum_edge']/n if n else 0):.3f}"
def probs_at_temp(entries,venue,temp):
 by=v24._entry_by_lane(entries);raw={i:v24._lane_raw_strength(by[i],i,venue) for i in range(1,7)}
 w={i:math.exp(raw[i]/temp) for i in range(1,7)};tot=sum(w.values());out={}
 for a in range(1,7):
  pa=w[a]/tot;tb=tot-w[a]
  for b in range(1,7):
   if b==a:continue
   pb=w[b]/tb;tc=tb-w[b]
   for c in range(1,7):
    if c==a or c==b:continue
    out[f'{a}-{b}-{c}']=pa*pb*(w[c]/tc)
 return out

def main():
 if not DB:raise RuntimeError('DATABASE_URL is required')
 print(f'BAO_VAL_MODE=read_only_probability_first temp:{TEMP:.2f} test:{START}..{END}',flush=True)
 print('BAO_VAL_CALIBRATION_PROVENANCE=train_through_2025-12_only',flush=True)
 print('BAO_VAL_ODDS_CAVEAT=historical_price_not_proven_actionable_timestamp',flush=True)
 overall={n:acc() for _,_,n in BINS};oths={t:acc() for t in THRESH};monthly={}
 cur=date(START.year,START.month,1);pred_races=0;odds_races=0
 with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
  while cur<=END:
   mx=nextm(cur);a=max(START,cur);b=min(END+timedelta(days=1),mx);key=a.strftime('%Y-%m')
   with conn.cursor() as c:
    c.execute("set statement_timeout='120s'")
    c.execute("""select r.race_id,coalesce(r.venue_id,r.venue_code) venue_id from v2_races r where r.race_date >= %s and r.race_date < %s order by r.race_id""",(a,b));races=[dict(x) for x in c.fetchall()]
    c.execute("""select e.race_id,e.lane,e.racer_number,e.racer_class,e.racer_name,e.national_win_rate,e.national_place2_rate,e.local_win_rate,e.local_place2_rate,e.avg_st,e.motor_no,e.boat_no from v2_race_entries e join v2_races r on r.race_id=e.race_id where r.race_date >= %s and r.race_date < %s order by e.race_id,e.lane""",(a,b));ents=[dict(x) for x in c.fetchall()]
   eb=defaultdict(list)
   for e in ents:eb[str(e['race_id'])].append(e)
   preds={}
   for r in races:
    rid=str(r['race_id']);es=eb.get(rid,[])
    if len(es)!=6 or {int(x.get('lane') or 0) for x in es}!={1,2,3,4,5,6}:continue
    try:ps=probs_at_temp(es,str(r.get('venue_id') or '').zfill(2),TEMP)
    except Exception:continue
    if len(ps)==120 and abs(sum(ps.values())-1)<1e-10:preds[rid]=ps
   pred_races+=len(preds)
   with conn.cursor() as c:
    c.execute("""select o.race_id,o.ticket,o.odds from v2_odds_trifecta o join v2_races r on r.race_id=o.race_id where r.race_date >= %s and r.race_date < %s and o.odds is not null and o.odds > 1 order by o.race_id,o.ticket""",(a,b));odds=[dict(x) for x in c.fetchall()]
    c.execute("""select res.race_id,res.trifecta_ticket,coalesce(res.trifecta_payout_yen,res.trifecta_payout,0) payout from v2_results res join v2_races r on r.race_id=res.race_id where r.race_date >= %s and r.race_date < %s""",(a,b));res={str(x['race_id']):(nt(x['trifecta_ticket']),int(float(x['payout'] or 0))) for x in c.fetchall()}
   odds_races+=len({str(x['race_id']) for x in odds})
   mb={n:acc() for _,_,n in BINS};mt={t:acc() for t in THRESH}
   for o in odds:
    rid=str(o['race_id']);ticket=nt(o['ticket']);ps=preds.get(rid);rr=res.get(rid)
    if not ps or ticket not in ps or not rr:continue
    odd=float(o['odds']);edge=float(ps[ticket])*odd;hit=(ticket==rr[0]);payout=rr[1]
    bn=edge_bin(edge)
    if bn=='OTHER':continue
    add(mb[bn],rid,edge,hit,payout);add(overall[bn],rid,edge,hit,payout)
    for t in THRESH:
     if edge>=t:add(mt[t],rid,edge,hit,payout);add(oths[t],rid,edge,hit,payout)
   monthly[key]=(mb,mt)
   print(f'BAO_VAL_MONTH={key} predicted_races:{len(preds)} odds_races:{len({str(x["race_id"]) for x in odds})}',flush=True)
   for _,_,n in BINS:
    if mb[n]['n']:print(f'BAO_VAL_MONTH_BIN={key} edge:{n} '+fm(mb[n]),flush=True)
   for t in THRESH:
    if mt[t]['n']:print(f'BAO_VAL_MONTH_THRESHOLD={key} ge:{t:.2f} '+fm(mt[t]),flush=True)
   cur=mx
 print(f'BAO_VAL_COVERAGE=predicted_races:{pred_races} summed_month_odds_races:{odds_races}',flush=True)
 for _,_,n in BINS:
  if overall[n]['n']:print(f'BAO_VAL_ALL_BIN=edge:{n} '+fm(overall[n]),flush=True)
 for t in THRESH:
  if oths[t]['n']:print(f'BAO_VAL_ALL_THRESHOLD=ge:{t:.2f} '+fm(oths[t]),flush=True)
 print('BAO_VAL_POLICY=research_only_realtime_forward_confirmation_required',flush=True)
 print('BAO_VAL_NEXT=check_monotonicity_and_then_realtime_closing_odds_forward_shadow',flush=True)
 print('BAO_VAL_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__':main()
