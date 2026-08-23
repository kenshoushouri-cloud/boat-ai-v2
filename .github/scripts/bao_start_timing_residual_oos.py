# -*- coding: utf-8 -*-
"""Expanding OOS for exhibition start-timing rank beyond market+Motor2+exhibition-time.
Read-only only; no Production/Shadow/LINE changes.
"""
from __future__ import annotations
import math, os, re
from collections import defaultdict
from datetime import date, timedelta
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip(); START=date(2025,7,1); END=date(2026,8,22); HIST='historical'; EPS=1e-15
BETAS=(-0.06,-0.04,-0.02,0.0,0.01,0.02,0.03,0.04,0.05,0.06,0.08,0.10)
SPLITS=[(date(2025,12,31),date(2026,1,1),date(2026,2,28),.08),(date(2026,2,28),date(2026,3,1),date(2026,4,30),.08),(date(2026,4,30),date(2026,5,1),date(2026,6,30),.08),(date(2026,6,30),date(2026,7,1),END,.06)]
CUT={x[0]:i for i,x in enumerate(SPLITS)}; POS=(1.,.6,.3); EXB=.06; MBS=sorted({x[3] for x in SPLITS})

def nt(v):
 xs=re.findall(r'[1-6]',str(v or '')); return '-'.join(xs[:3]) if len(xs)>=3 else ''
def nextm(d): return date(d.year+1,1,1) if d.month==12 else date(d.year,d.month+1,1)
def sf(v):
 try:return None if v in (None,'') else float(v)
 except:return None
def zs(vals):
 mu=sum(vals)/6.; sd=math.sqrt(sum((x-mu)**2 for x in vals)/6.)
 return None if sd<1e-12 else {i+1:(vals[i]-mu)/sd for i in range(6)}
def scores(entries,xrows):
 eb={int(x.get('lane') or 0):x for x in entries}; xb={int(x.get('lane') or 0):x for x in xrows}
 if set(eb)!={1,2,3,4,5,6} or set(xb)!={1,2,3,4,5,6}:return None
 mv=[]; ev=[]; sv=[]
 for l in range(1,7):
  m=sf(eb[l].get('motor_place2_rate')); er=sf(xb[l].get('exhibition_time_rank')); sr=sf(xb[l].get('start_timing_rank'))
  if m is None or not 0<=m<=100 or er is None or int(er) not in range(1,7) or sr is None or int(sr) not in range(1,7):return None
  mv.append(m);ev.append(-er);sv.append(-sr)
 zm,ze,zs_=zs(mv),zs(ev),zs(sv)
 if not zm or not ze or not zs_:return None
 sm={};se={};ss={}
 for a in range(1,7):
  for b in range(1,7):
   if b==a:continue
   for c in range(1,7):
    if c in (a,b):continue
    t=f'{a}-{b}-{c}'
    sm[t]=POS[0]*zm[a]+POS[1]*zm[b]+POS[2]*zm[c]
    se[t]=POS[0]*ze[a]+POS[1]*ze[b]+POS[2]*ze[c]
    ss[t]=POS[0]*zs_[a]+POS[1]*zs_[b]+POS[2]*zs_[c]
 return sm,se,ss

def adj(q,sm,se,ss,bm,bs):
 v={t:x*math.exp(bm*sm[t]+EXB*se[t]+bs*ss[t]) for t,x in q.items()}; z=sum(v.values()); return {t:x/z for t,x in v.items()}
def stat():return {'n':0,'ds':0.,'d2':0.,'bl':0.,'jl':0.}
def add(s,b,j,a):
 lb=-math.log(max(b[a],EPS));lj=-math.log(max(j[a],EPS));d=lj-lb;s['n']+=1;s['bl']+=lb;s['jl']+=lj;s['ds']+=d;s['d2']+=d*d
def fmt(s):
 n=s['n'];
 if not n:return 'n:0'
 d=s['ds']/n;var=max(0.,(s['d2']-s['ds']**2/n)/(n-1)) if n>1 else 0.;se=math.sqrt(var/n);z=d/se if se else 0.
 return f"n:{n} base_ll:{s['bl']/n:.6f} joint_ll:{s['jl']/n:.6f} delta_ll:{d:.6f} se:{se:.6f} z:{z:.2f}"
def split_for(d):
 for i,(_,a,b,_) in enumerate(SPLITS):
  if a<=d<=b:return i
 return None

def main():
 if not DB:raise RuntimeError('DATABASE_URL is required')
 print(f'BAO_ST_OOS_MODE=read_only period:{START}..{END}',flush=True);print('BAO_ST_OOS_BASELINE=devig_market_plus_motor2_plus_exhibition_time_beta_0.06',flush=True)
 tl={bm:{b:0. for b in BETAS} for bm in MBS};tn={bm:0 for bm in MBS};sel=[None]*4;sp=[stat() for _ in SPLITS];mo=defaultdict(stat);total=ready=0
 with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
  cur=date(START.year,START.month,1)
  while cur<=END:
   mx=nextm(cur);a=max(cur,START);b=min(mx,END+timedelta(days=1))
   with conn.cursor() as c:
    c.execute("set statement_timeout='180s'")
    c.execute('select race_id,race_date from v2_races where race_date>=%s and race_date<%s order by race_id',(a,b));races=[dict(x) for x in c.fetchall()]
    c.execute('''select e.race_id,e.lane,e.motor_place2_rate from v2_race_entries e join v2_races r on r.race_id=e.race_id where r.race_date>=%s and r.race_date<%s''',(a,b));er=[dict(x) for x in c.fetchall()]
    c.execute('''select x.race_id,x.lane,x.exhibition_time_rank,x.start_timing_rank from v2_realtime_exhibition_snapshots x join v2_races r on r.race_id=x.race_id where r.race_date>=%s and r.race_date<%s and x.snapshot_label=%s''',(a,b,HIST));xr=[dict(x) for x in c.fetchall()]
    c.execute('''select o.race_id,o.ticket,o.odds from v2_odds_trifecta o join v2_races r on r.race_id=o.race_id where r.race_date>=%s and r.race_date<%s and o.odds>1''',(a,b));oo=[dict(x) for x in c.fetchall()]
    c.execute('''select res.race_id,res.trifecta_ticket from v2_results res join v2_races r on r.race_id=res.race_id where r.race_date>=%s and r.race_date<%s''',(a,b));rr={str(x['race_id']):nt(x['trifecta_ticket']) for x in c.fetchall()}
   eb=defaultdict(list);xb=defaultdict(list);ob=defaultdict(dict)
   for x in er:eb[str(x['race_id'])].append(x)
   for x in xr:xb[str(x['race_id'])].append(x)
   for x in oo:
    t=nt(x['ticket']);
    if t:ob[str(x['race_id'])][t]=float(x['odds'])
   mok=0;total+=len(races)
   for r in races:
    rid=str(r['race_id']);actual=rr.get(rid,'');om=ob.get(rid,{});sc=scores(eb.get(rid,[]),xb.get(rid,[]))
    if sc is None or len(om)!=120 or actual not in om:continue
    inv={t:1./o for t,o in om.items() if o>1}
    if len(inv)!=120:continue
    z=sum(inv.values());q={t:v/z for t,v in inv.items()};sm,se,ss=sc;ready+=1;mok+=1
    for bm in MBS:
     for bs in BETAS:tl[bm][bs]+=-math.log(max(adj(q,sm,se,ss,bm,bs)[actual],EPS))
     tn[bm]+=1
    si=split_for(r['race_date'])
    if si is not None and sel[si] is not None:
     bm=SPLITS[si][3];base=adj(q,sm,se,ss,bm,0.);joint=adj(q,sm,se,ss,bm,sel[si]);add(sp[si],base,joint,actual);add(mo[r['race_date'].strftime('%Y-%m')],base,joint,actual)
   print(f"BAO_ST_MONTH_COVERAGE={a.strftime('%Y-%m')} ready:{mok}/{len(races)}",flush=True)
   cutoff=b-timedelta(days=1)
   if cutoff in CUT:
    si=CUT[cutoff];bm=SPLITS[si][3];best=min(BETAS,key=lambda x:tl[bm][x]/max(tn[bm],1));sel[si]=best;top=sorted(BETAS,key=lambda x:tl[bm][x]/max(tn[bm],1))[:5]
    print(f"BAO_ST_SELECT=split:{si+1} train_end:{cutoff} motor:{bm:.2f} exhibition:{EXB:.2f} start_beta:{best:.2f} n:{tn[bm]} top:"+','.join(f'{x:.2f}:{tl[bm][x]/max(tn[bm],1):.6f}' for x in top),flush=True)
   cur=mx
 print(f'BAO_ST_COVERAGE=total:{total} ready:{ready}',flush=True);all_=stat()
 for i,(_,a,b,bm) in enumerate(SPLITS):
  print(f'BAO_ST_SPLIT={i+1} test:{a}..{b} motor:{bm:.2f} exhibition:{EXB:.2f} start:{sel[i]:.2f} {fmt(sp[i])}',flush=True)
  for k in all_:all_[k]+=sp[i][k]
 neg=0
 for k in sorted(mo):
  s=mo[k];neg+=int(s['n'] and s['ds']/s['n']<0);print(f'BAO_ST_MONTH={k} {fmt(s)}',flush=True)
 print('BAO_ST_SELECTED_BETAS='+','.join(f'{x:.2f}' for x in sel),flush=True);print(f'BAO_ST_MONTH_STABILITY=negative:{neg}/{len(mo)}',flush=True);print('BAO_ST_ALL='+fmt(all_),flush=True)
 n=all_['n'];d=all_['ds']/n if n else 0.;var=max(0.,(all_['d2']-all_['ds']**2/n)/(n-1)) if n>1 else 0.;se=math.sqrt(var/n) if n else 0.;robust=n>0 and d<0 and all(x is not None and x>0 for x in sel) and neg>=max(6,len(mo)-2) and (se==0 or d/se<=-2)
 print('BAO_ST_VERDICT='+('ROBUST_CANDIDATE' if robust else 'NOT_YET_ROBUST'),flush=True);print('BAO_ST_POLICY=no_production_change',flush=True);print('BAO_ST_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__':main()
