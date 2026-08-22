# -*- coding: utf-8 -*-
"""Train-only probability-temperature calibration with expanding OOS tests.

Uses the current v24 lane-strength model but never reads odds. For each split,
PROB_TEMP is selected using only prior races by minimum multiclass log loss,
then frozen for the future test window. Production constant remains unchanged.

Read-only, no DB writes, no Production/Shadow/LINE changes.
"""
from __future__ import annotations
import math, os, re
from collections import defaultdict
from datetime import date
from statistics import mean
import psycopg
from psycopg.rows import dict_row
import v24_pre_candidate_notifier_pg as v24

DB=os.getenv('DATABASE_URL','').strip()
START='2025-07-01'; END='2026-08-22'
TEMPS=[0.80,1.00,1.20,1.40,1.60,1.80,2.00,2.20,2.40,2.60,3.00]
SPLITS=[
 ('2025-12-31','2026-01-01','2026-02-28'),
 ('2026-02-28','2026-03-01','2026-04-30'),
 ('2026-04-30','2026-05-01','2026-06-30'),
 ('2026-06-30','2026-07-01','2026-08-22'),
]

def nt(v):
 x=re.findall(r'[1-6]',str(v or ''));return tuple(int(n) for n in x[:3]) if len(x)>=3 else None

def ticket_probs(raw,temp):
 w={i:math.exp(raw[i]/temp) for i in range(1,7)};total=sum(w.values());out={}
 for a in range(1,7):
  pa=w[a]/total;tb=total-w[a]
  for b in range(1,7):
   if b==a:continue
   pb=w[b]/tb;tc=tb-w[b]
   for c in range(1,7):
    if c==a or c==b:continue
    out[(a,b,c)]=pa*pb*(w[c]/tc)
 return out

def actual_prob(raw,ticket,temp):
 a,b,c=ticket;w={i:math.exp(raw[i]/temp) for i in range(1,7)};tot=sum(w.values())
 return (w[a]/tot)*(w[b]/(tot-w[a]))*(w[c]/(tot-w[a]-w[b]))

def eval_rows(rows,temp,full=False):
 ll=[];br=[];pa=[]
 for _,raw,t in rows:
  p=max(actual_prob(raw,t,temp),1e-15);pa.append(p);ll.append(-math.log(p))
  if full:
   ps=ticket_probs(raw,temp);br.append(sum((q-(1.0 if k==t else 0.0))**2 for k,q in ps.items()))
 return {'n':len(rows),'logloss':mean(ll) if ll else 0.,'brier':mean(br) if br else None,'pactual':mean(pa) if pa else 0.}

def main():
 if not DB:raise RuntimeError('DATABASE_URL is required')
 print(f'BAO_TEMP_MODE=read_only_odds_free period:{START}..{END}',flush=True)
 print('BAO_TEMP_GRID='+','.join(f'{x:.2f}' for x in TEMPS),flush=True)
 with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
  with conn.cursor() as c:
   c.execute("set statement_timeout='120s'")
   c.execute("""select r.race_id,r.race_date,coalesce(r.venue_id,r.venue_code) venue_id
                from v2_races r where r.race_date between %s and %s order by r.race_date,r.race_id""",(START,END));races=[dict(x) for x in c.fetchall()]
   c.execute("""select e.race_id,e.lane,e.racer_number,e.racer_class,e.racer_name,e.national_win_rate,e.national_place2_rate,e.local_win_rate,e.local_place2_rate,e.avg_st,e.motor_no,e.boat_no
                from v2_race_entries e join v2_races r on r.race_id=e.race_id where r.race_date between %s and %s order by e.race_id,e.lane""",(START,END));ents=[dict(x) for x in c.fetchall()]
   c.execute("""select res.race_id,res.trifecta_ticket from v2_results res join v2_races r on r.race_id=res.race_id where r.race_date between %s and %s""",(START,END));results={str(x['race_id']):nt(x['trifecta_ticket']) for x in c.fetchall()}
 eb=defaultdict(list)
 for e in ents:eb[str(e['race_id'])].append(e)
 rows=[];bad=0
 for r in races:
  rid=str(r['race_id']);es=eb.get(rid,[]);ticket=results.get(rid)
  if len(es)!=6 or ticket is None:continue
  by=v24._entry_by_lane(es)
  if set(by)!={1,2,3,4,5,6}:continue
  venue=str(r.get('venue_id') or '').zfill(2)
  try:raw={lane:v24._lane_raw_strength(by[lane],lane,venue) for lane in range(1,7)}
  except Exception:bad+=1;continue
  rows.append((str(r['race_date']),raw,ticket))
 print(f'BAO_TEMP_ROWS={len(rows)} bad:{bad}',flush=True)
 if len(rows)<50000:raise SystemExit('insufficient historical rows')
 for i,(train_end,test_start,test_end) in enumerate(SPLITS,1):
  train=[x for x in rows if x[0]<=train_end];test=[x for x in rows if test_start<=x[0]<=test_end]
  train_scores=[]
  for t in TEMPS:
   m=eval_rows(train,t,False);train_scores.append((m['logloss'],t))
  train_scores.sort();best_ll,best_t=train_scores[0]
  base_train=eval_rows(train,2.20,False);base=eval_rows(test,2.20,True);cal=eval_rows(test,best_t,True)
  print(f'BAO_TEMP_SPLIT={i} train_end:{train_end} test:{test_start}..{test_end} train_n:{len(train)} test_n:{len(test)} selected_temp:{best_t:.2f} train_logloss:{best_ll:.6f} train_base22:{base_train["logloss"]:.6f}',flush=True)
  print(f'BAO_TEMP_TEST_BASE={i} temp:2.20 logloss:{base["logloss"]:.6f} brier:{base["brier"]:.6f} mean_p_actual:{base["pactual"]:.6f}',flush=True)
  print(f'BAO_TEMP_TEST_CAL={i} temp:{best_t:.2f} logloss:{cal["logloss"]:.6f} brier:{cal["brier"]:.6f} mean_p_actual:{cal["pactual"]:.6f}',flush=True)
  print(f'BAO_TEMP_TEST_DELTA={i} logloss:{cal["logloss"]-base["logloss"]:+.6f} brier:{cal["brier"]-base["brier"]:+.6f}',flush=True)
  top5=sorted((eval_rows(train,t,False)['logloss'],t) for t in TEMPS)[:5]
  print('BAO_TEMP_TRAIN_TOP='+str(i)+' '+','.join(f'{t:.2f}:{ll:.6f}' for ll,t in top5),flush=True)
 print('BAO_TEMP_POLICY=no_production_change_from_this_audit',flush=True)
 print('BAO_TEMP_NEXT=if_oos_consistent_use_calibrated_temp_in_separate_full_market_value_replay',flush=True)
 print('BAO_TEMP_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__':main()
