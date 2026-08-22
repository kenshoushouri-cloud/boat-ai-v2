# -*- coding: utf-8 -*-
"""Fine-grid robustness audit for exhibition-time rank beyond market + Motor2.

Motor2 coefficients are fixed per future split to the train-only values already
validated in PR #108.  Only the extra exhibition-time coefficient is selected
on prior races and frozen into the future OOS window.

Read-only research; no DB writes, Production, Shadow or LINE changes.
"""
from __future__ import annotations
import math, os, re
from collections import defaultdict
from datetime import date, timedelta
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip(); START=date(2025,7,1); END=date(2026,8,22); HIST='historical'; EPS=1e-15
BETAS=(-0.02,0.00,0.01,0.02,0.03,0.04,0.05,0.06,0.08,0.10,0.12)
SPLITS=[
 (date(2025,12,31),date(2026,1,1),date(2026,2,28),0.08),
 (date(2026,2,28),date(2026,3,1),date(2026,4,30),0.08),
 (date(2026,4,30),date(2026,5,1),date(2026,6,30),0.08),
 (date(2026,6,30),date(2026,7,1),END,0.06),
]
CUT={x[0]:i for i,x in enumerate(SPLITS)}; POS=(1.0,.6,.3); MBS=sorted({x[3] for x in SPLITS})

def nt(v):
 xs=re.findall(r'[1-6]',str(v or '')); return '-'.join(xs[:3]) if len(xs)>=3 else ''
def nextm(d): return date(d.year+1,1,1) if d.month==12 else date(d.year,d.month+1,1)
def sf(v):
 try:return None if v in (None,'') else float(v)
 except:return None
def zscore(vals):
 mu=sum(vals)/6.; sd=math.sqrt(sum((x-mu)**2 for x in vals)/6.)
 return None if sd<1e-12 else {i+1:(vals[i]-mu)/sd for i in range(6)}
def scores(entries,xrows):
 eb={int(x.get('lane') or 0):x for x in entries}; xb={int(x.get('lane') or 0):x for x in xrows}
 if set(eb)!={1,2,3,4,5,6} or set(xb)!={1,2,3,4,5,6}:return None
 mv=[]; xv=[]
 for l in range(1,7):
  m=sf(eb[l].get('motor_place2_rate')); r=sf(xb[l].get('exhibition_time_rank'))
  if m is None or not 0<=m<=100 or r is None or int(r) not in range(1,7):return None
  mv.append(m); xv.append(-r)
 zm,zx=zscore(mv),zscore(xv)
 if not zm or not zx:return None
 sm={}; sx={}
 for a in range(1,7):
  for b in range(1,7):
   if b==a:continue
   for c in range(1,7):
    if c in (a,b):continue
    t=f'{a}-{b}-{c}'; sm[t]=POS[0]*zm[a]+POS[1]*zm[b]+POS[2]*zm[c]; sx[t]=POS[0]*zx[a]+POS[1]*zx[b]+POS[2]*zx[c]
 return sm,sx

def adj(q,sm,sx,bm,bx):
 vals={t:qq*math.exp(bm*sm[t]+bx*sx[t]) for t,qq in q.items()}; s=sum(vals.values()); return {t:v/s for t,v in vals.items()}
def loss(q,sm,sx,a,bm,bx): return -math.log(max(adj(q,sm,sx,bm,bx)[a],EPS))
def stat_new():return {'n':0,'bll':0.,'jll':0.,'bbr':0.,'jbr':0.,'brk':0.,'jrk':0.,'ds':0.,'d2':0.}
def stat_add(s,b,j,a):
 pb=max(b[a],EPS); pj=max(j[a],EPS); lb=-math.log(pb); lj=-math.log(pj); d=lj-lb
 s['n']+=1;s['bll']+=lb;s['jll']+=lj;s['bbr']+=1-2*pb+sum(x*x for x in b.values());s['jbr']+=1-2*pj+sum(x*x for x in j.values());s['brk']+=1+sum(x>pb for x in b.values());s['jrk']+=1+sum(x>pj for x in j.values());s['ds']+=d;s['d2']+=d*d
def merge(a,b):
 for k in a:a[k]+=b[k]
def fmt(s):
 n=s['n'];
 if not n:return 'n:0'
 d=s['ds']/n; var=max(0.,(s['d2']-s['ds']*s['ds']/n)/(n-1)) if n>1 else 0.; se=math.sqrt(var/n) if n else 0.; z=d/se if se>0 else 0.
 return f"n:{n} base_ll:{s['bll']/n:.6f} joint_ll:{s['jll']/n:.6f} delta_ll:{d:.6f} se:{se:.6f} z:{z:.2f} delta_brier:{s['jbr']/n-s['bbr']/n:.6f} delta_rank:{s['jrk']/n-s['brk']/n:.2f}"
def split_for(d):
 for i,(_,a,b,_) in enumerate(SPLITS):
  if a<=d<=b:return i
 return None

def main():
 if not DB:raise RuntimeError('DATABASE_URL is required')
 print(f'BAO_EXROB_MODE=read_only period:{START}..{END} label:{HIST}',flush=True);print('BAO_EXROB_BASELINE=devig_market_plus_pr108_motor2',flush=True);print('BAO_EXROB_BETA_GRID='+','.join(f'{x:.2f}' for x in BETAS),flush=True)
 tl={bm:{b:0. for b in BETAS} for bm in MBS}; tn={bm:0 for bm in MBS}; selected=[None]*4; split=[stat_new() for _ in SPLITS]; months=defaultdict(stat_new); venues=defaultdict(stat_new); total=ready=0
 with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
  cur=date(START.year,START.month,1)
  while cur<=END:
   mx=nextm(cur); a=max(cur,START); b=min(mx,END+timedelta(days=1))
   with conn.cursor() as c:
    c.execute("set statement_timeout='180s'")
    c.execute('select race_id,race_date,coalesce(venue_id,venue_code) venue_id from v2_races where race_date>=%s and race_date<%s order by race_id',(a,b)); races=[dict(x) for x in c.fetchall()]
    c.execute('''select e.race_id,e.lane,e.motor_place2_rate from v2_race_entries e join v2_races r on r.race_id=e.race_id where r.race_date>=%s and r.race_date<%s order by e.race_id,e.lane''',(a,b)); er=[dict(x) for x in c.fetchall()]
    c.execute('''select x.race_id,x.lane,x.exhibition_time_rank from v2_realtime_exhibition_snapshots x join v2_races r on r.race_id=x.race_id where r.race_date>=%s and r.race_date<%s and x.snapshot_label=%s order by x.race_id,x.lane''',(a,b,HIST)); xr=[dict(x) for x in c.fetchall()]
    c.execute('''select o.race_id,o.ticket,o.odds from v2_odds_trifecta o join v2_races r on r.race_id=o.race_id where r.race_date>=%s and r.race_date<%s and o.odds>1 order by o.race_id,o.ticket''',(a,b)); oo=[dict(x) for x in c.fetchall()]
    c.execute('''select res.race_id,res.trifecta_ticket from v2_results res join v2_races r on r.race_id=res.race_id where r.race_date>=%s and r.race_date<%s''',(a,b)); rr={str(x['race_id']):nt(x['trifecta_ticket']) for x in c.fetchall()}
   eb=defaultdict(list);xb=defaultdict(list);ob=defaultdict(dict)
   for x in er:eb[str(x['race_id'])].append(x)
   for x in xr:xb[str(x['race_id'])].append(x)
   for x in oo:
    t=nt(x['ticket']);
    if t:ob[str(x['race_id'])][t]=float(x['odds'])
   mok=0; total+=len(races)
   for r in races:
    rid=str(r['race_id']); actual=rr.get(rid,''); om=ob.get(rid,{}); sc=scores(eb.get(rid,[]),xb.get(rid,[]))
    if sc is None or len(om)!=120 or actual not in om:continue
    inv={t:1./o for t,o in om.items() if o>1};
    if len(inv)!=120:continue
    q={t:v/sum(inv.values()) for t,v in inv.items()}; sm,sx=sc; ready+=1;mok+=1
    for bm in MBS:
     for bx in BETAS:tl[bm][bx]+=loss(q,sm,sx,actual,bm,bx)
     tn[bm]+=1
    si=split_for(r['race_date'])
    if si is not None and selected[si] is not None:
     bm=SPLITS[si][3]; base=adj(q,sm,sx,bm,0.); joint=adj(q,sm,sx,bm,selected[si]); stat_add(split[si],base,joint,actual);stat_add(months[r['race_date'].strftime('%Y-%m')],base,joint,actual);stat_add(venues[str(r.get('venue_id') or '').zfill(2)],base,joint,actual)
   print(f"BAO_EXROB_MONTH_COVERAGE={a.strftime('%Y-%m')} ready:{mok}/{len(races)}",flush=True)
   cutoff=b-timedelta(days=1)
   if cutoff in CUT:
    si=CUT[cutoff]; bm=SPLITS[si][3]; best=min(BETAS,key=lambda x:tl[bm][x]/max(tn[bm],1));selected[si]=best;top=sorted(BETAS,key=lambda x:tl[bm][x]/max(tn[bm],1))[:5];print(f"BAO_EXROB_SELECT=split:{si+1} train_end:{cutoff} motor_beta:{bm:.2f} extra_beta:{best:.2f} n:{tn[bm]} top:"+','.join(f'{x:.2f}:{tl[bm][x]/max(tn[bm],1):.6f}' for x in top),flush=True)
   cur=mx
 print(f'BAO_EXROB_COVERAGE=total:{total} ready:{ready}',flush=True); overall=stat_new()
 for i,(_,a,b,bm) in enumerate(SPLITS):print(f'BAO_EXROB_SPLIT={i+1} test:{a}..{b} motor_beta:{bm:.2f} extra_beta:{selected[i]:.2f} {fmt(split[i])}',flush=True);merge(overall,split[i])
 negm=totm=0
 for k in sorted(months):
  s=months[k];totm+=1;negm+=int(s['ds']/s['n']<0);print(f'BAO_EXROB_MONTH={k} {fmt(s)}',flush=True)
 negv=totv=0
 for v in sorted(venues):
  s=venues[v]
  if s['n']>=500:totv+=1;negv+=int(s['ds']/s['n']<0);print(f'BAO_EXROB_VENUE={v} {fmt(s)}',flush=True)
 print('BAO_EXROB_SELECTED_BETAS='+','.join(f'{x:.2f}' for x in selected),flush=True);print(f'BAO_EXROB_STABILITY=negative_delta_months:{negm}/{totm} negative_delta_venues_n500:{negv}/{totv}',flush=True);print('BAO_EXROB_ALL='+fmt(overall),flush=True)
 n=overall['n'];d=overall['ds']/n if n else 0.;var=max(0.,(overall['d2']-overall['ds']**2/n)/(n-1)) if n>1 else 0.;se=math.sqrt(var/n) if n else 0.;robust=n>0 and d<0 and all(x is not None and x>0 for x in selected) and negm>=max(6,totm-2) and (se==0 or d/se<=-2)
 print('BAO_EXROB_VERDICT='+('ROBUST_CANDIDATE' if robust else 'NOT_YET_ROBUST'),flush=True);print('BAO_EXROB_POLICY=no_production_change',flush=True);print('BAO_EXROB_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__':main()
