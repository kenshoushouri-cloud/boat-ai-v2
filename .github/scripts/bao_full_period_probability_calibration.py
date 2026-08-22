# -*- coding: utf-8 -*-
"""Full-period odds-free calibration audit of current v24 120-ticket model.

Processes one month at a time so millions of ticket probabilities are never
persisted. Only aggregate metrics are kept in memory/logs.

No odds queries. No DB writes. No Production/Shadow/LINE changes.
"""
from __future__ import annotations
import math, os, re
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
import psycopg
from psycopg.rows import dict_row
import v24_pre_candidate_notifier_pg as v24

DB=os.getenv('DATABASE_URL','').strip()
START=date.fromisoformat(os.getenv('BAO_CAL_START','2025-07-01'))
END=date.fromisoformat(os.getenv('BAO_CAL_END','2026-08-22'))
BINS=[(0,.0025,'LT0.25%'),(.0025,.005,'0.25-0.5%'),(.005,.01,'0.5-1%'),(.01,.02,'1-2%'),(.02,.03,'2-3%'),(.03,.05,'3-5%'),(.05,1.01,'GE5%')]

def nt(v):
 x=re.findall(r'[1-6]',str(v or ''));return '-'.join(x[:3]) if len(x)>=3 else str(v or '').strip()
def pbin(p):
 for a,b,n in BINS:
  if a<=p<b:return n
 return 'OTHER'
def next_month(d): return date(d.year+1,1,1) if d.month==12 else date(d.year,d.month+1,1)
def metrics_acc():return {'races':0,'eval':0,'sum_pa':0.,'sum_rank':0.,'top1':0,'top3':0,'top10':0,'sum_brier':0.,'sum_log':0.}
def addm(m,pa,rank,brier,ll):
 m['eval']+=1;m['sum_pa']+=pa;m['sum_rank']+=rank;m['top1']+=rank<=1;m['top3']+=rank<=3;m['top10']+=rank<=10;m['sum_brier']+=brier;m['sum_log']+=ll
def fmt(m):
 n=m['eval']
 if not n:return 'eval:0'
 return f"eval:{n} mean_p_actual:{m['sum_pa']/n:.6f} mean_rank:{m['sum_rank']/n:.2f} top1:{m['top1']}/{n} top3:{m['top3']}/{n} top10:{m['top10']}/{n} brier:{m['sum_brier']/n:.6f} logloss:{m['sum_log']/n:.6f}"

def main():
 if not DB:raise RuntimeError('DATABASE_URL is required')
 print(f'BAO_FPC_MODE=read_only_odds_free period:{START}..{END}',flush=True)
 print('BAO_FPC_STORAGE=aggregate_only_no_probability_persistence',flush=True)
 allm=metrics_acc();cal=defaultdict(lambda:{'n':0,'expected':0.,'hits':0});struct={'races':0,'complete':0,'malformed':0,'sum_fail':0,'result_missing':0}
 cur=date(START.year,START.month,1)
 with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
  while cur<=END:
   mx=next_month(cur);a=max(START,cur);b=min(END+timedelta(days=1),mx)
   if a>=b:cur=mx;continue
   with conn.cursor() as c:
    c.execute("set statement_timeout='120s'")
    c.execute("""select r.race_id,r.race_date,coalesce(r.venue_id,r.venue_code) venue_id,r.race_no
                 from v2_races r where r.race_date >= %s and r.race_date < %s order by r.race_date,venue_id,r.race_no""",(a,b));races=[dict(x) for x in c.fetchall()]
    c.execute("""select e.race_id,e.lane,e.racer_number,e.racer_class,e.racer_name,e.national_win_rate,e.national_place2_rate,e.local_win_rate,e.local_place2_rate,e.avg_st,e.motor_no,e.boat_no
                 from v2_race_entries e join v2_races r on r.race_id=e.race_id where r.race_date >= %s and r.race_date < %s order by e.race_id,e.lane""",(a,b));ents=[dict(x) for x in c.fetchall()]
    # Result retrieval stays logically separate from probability generation below.
   eb=defaultdict(list)
   for e in ents:eb[str(e['race_id'])].append(e)
   preds={};mm=metrics_acc();mm['races']=len(races);struct['races']+=len(races)
   for r in races:
    rid=str(r['race_id']);es=eb.get(rid,[])
    if len(es)!=6 or {int(x.get('lane') or 0) for x in es}!={1,2,3,4,5,6}:continue
    try:ps=v24._ticket_probabilities(es,str(r.get('venue_id') or '').zfill(2))
    except Exception:struct['malformed']+=1;continue
    if len(ps)!=120:struct['malformed']+=1;continue
    if abs(sum(ps.values())-1)>1e-10:struct['sum_fail']+=1;continue
    preds[rid]=ps;struct['complete']+=1
   with conn.cursor() as c:
    c.execute("""select res.race_id,res.trifecta_ticket from v2_results res join v2_races r on r.race_id=res.race_id where r.race_date >= %s and r.race_date < %s""",(a,b));res={str(x['race_id']):nt(x['trifecta_ticket']) for x in c.fetchall()}
   for rid,ps in preds.items():
    actual=res.get(rid,'')
    if actual not in ps:struct['result_missing']+=1;continue
    ranked=sorted(ps.items(),key=lambda z:z[1],reverse=True);rank=1+next(i for i,(t,_) in enumerate(ranked) if t==actual);pa=float(ps[actual])
    br=sum((float(p)-(1. if t==actual else 0.))**2 for t,p in ps.items());ll=-math.log(max(pa,1e-15))
    addm(mm,pa,rank,br,ll);addm(allm,pa,rank,br,ll)
    for t,p in ps.items():
     q=cal[pbin(float(p))];q['n']+=1;q['expected']+=float(p);q['hits']+=int(t==actual)
   print(f'BAO_FPC_MONTH={a.strftime("%Y-%m")} races:{len(races)} '+fmt(mm),flush=True)
   cur=mx
 print('BAO_FPC_ALL='+fmt(allm),flush=True)
 uniform_ll=math.log(120);uniform_br=(1-1/120)**2+119*(1/120)**2
 print(f'BAO_FPC_UNIFORM_BASELINE=brier:{uniform_br:.6f} logloss:{uniform_ll:.6f}',flush=True)
 for _,_,name in BINS:
  q=cal[name]
  if not q['n']:continue
  actual=q['hits']/q['n'];pred=q['expected']/q['n'];ratio=(actual/pred if pred else 0.)
  print(f"BAO_FPC_CAL_BIN={name} n:{q['n']} predicted:{pred:.6f} actual:{actual:.6f} hits:{q['hits']} expected_hits:{q['expected']:.1f} actual_to_pred:{ratio:.3f}",flush=True)
 print(f"BAO_FPC_STRUCTURE=races:{struct['races']} complete:{struct['complete']} malformed:{struct['malformed']} sum_fail:{struct['sum_fail']} result_missing:{struct['result_missing']}",flush=True)
 ok=allm['eval']>=50000 and struct['malformed']==0 and struct['sum_fail']==0
 print(f"BAO_FPC_READINESS={'READY_FOR_CALIBRATION_MODEL' if ok else 'LIMITED'}",flush=True)
 print('BAO_FPC_NEXT=train_only_calibration_then_separate_historical_odds_edge_oos',flush=True)
 print('BAO_FPC_RESULT=PASS_READ_ONLY' if ok else 'BAO_FPC_RESULT=PASS_LIMITED',flush=True)
if __name__=='__main__':main()
