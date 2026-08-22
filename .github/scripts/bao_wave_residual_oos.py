# -*- coding: utf-8 -*-
"""Train-only expanding OOS audit for wave residual beyond market+Motor2+exhibition.

Read-only. No DB writes, Production, Shadow or LINE changes.
"""
from __future__ import annotations
import math, os, re
from collections import defaultdict
from datetime import date, timedelta
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip(); START=date(2025,7,1); END=date(2026,8,22); HIST='historical'; EPS=1e-15
SPLITS=[
 (date(2025,12,31),date(2026,1,1),date(2026,2,28),0.08,0.06),
 (date(2026,2,28),date(2026,3,1),date(2026,4,30),0.08,0.06),
 (date(2026,4,30),date(2026,5,1),date(2026,6,30),0.08,0.06),
 (date(2026,6,30),date(2026,7,1),END,0.06,0.06),
]
WGRID=(0.0,0.25,0.5,0.75,1.0,1.25); POS=(1.0,.6,.3); SHRINK_K=50.0; MIN_BUCKET=30; MIN_BASE=100

def nt(v):
 xs=re.findall(r'[1-6]',str(v or '')); return '-'.join(xs[:3]) if len(xs)>=3 else ''
def nextm(d): return date(d.year+1,1,1) if d.month==12 else date(d.year,d.month+1,1)
def sf(v):
 try:return None if v in (None,'') else float(v)
 except:return None
def wb(v):
 x=float(v); return '<3' if x<3 else ('3-<6' if x<6 else ('6-<10' if x<10 else '10+'))
def logit(p):
 p=min(1-1e-6,max(1e-6,p)); return math.log(p/(1-p))
def zscore(vals):
 mu=sum(vals)/6.; sd=math.sqrt(sum((x-mu)**2 for x in vals)/6.); return None if sd<1e-12 else {i+1:(vals[i]-mu)/sd for i in range(6)}
def entry_scores(entries,xrows):
 eb={int(x.get('lane') or 0):x for x in entries}; xb={int(x.get('lane') or 0):x for x in xrows}
 if set(eb)!={1,2,3,4,5,6} or set(xb)!={1,2,3,4,5,6}:return None
 mv=[]; xv=[]
 for l in range(1,7):
  m=sf(eb[l].get('motor_place2_rate')); r=sf(xb[l].get('exhibition_time_rank'))
  if m is None or not 0<=m<=100 or r is None or int(r) not in range(1,7):return None
  mv.append(m);xv.append(-r)
 zm,zx=zscore(mv),zscore(xv)
 if not zm or not zx:return None
 sm={};sx={}
 for a in range(1,7):
  for b in range(1,7):
   if b==a:continue
   for c in range(1,7):
    if c in (a,b):continue
    t=f'{a}-{b}-{c}';sm[t]=POS[0]*zm[a]+POS[1]*zm[b]+POS[2]*zm[c];sx[t]=POS[0]*zx[a]+POS[1]*zx[b]+POS[2]*zx[c]
 return sm,sx
def wave_score(profile,venue,bucket):
 lane={l:profile.get((venue,l,bucket),0.0) for l in range(1,7)}; out={}
 for a in range(1,7):
  for b in range(1,7):
   if b==a:continue
   for c in range(1,7):
    if c in (a,b):continue
    out[f'{a}-{b}-{c}']=POS[0]*lane[a]+POS[1]*lane[b]+POS[2]*lane[c]
 return out
def adj(q,sm,sx,sw,bm,bx,bw):
 vals={t:qq*math.exp(bm*sm[t]+bx*sx[t]+bw*sw[t]) for t,qq in q.items()};s=sum(vals.values());return {t:v/s for t,v in vals.items()}
def stat_new():return {'n':0,'base':0.,'joint':0.,'ds':0.,'d2':0.}
def stat_add(s,b,j,a):
 lb=-math.log(max(b[a],EPS));lj=-math.log(max(j[a],EPS));d=lj-lb;s['n']+=1;s['base']+=lb;s['joint']+=lj;s['ds']+=d;s['d2']+=d*d
def merge(a,b):
 for k in a:a[k]+=b[k]
def fmt(s):
 n=s['n'];
 if not n:return 'n:0'
 d=s['ds']/n;var=max(0.,(s['d2']-s['ds']*s['ds']/n)/(n-1)) if n>1 else 0.;se=math.sqrt(var/n) if n else 0.;z=d/se if se else 0.
 return f"n:{n} base_ll:{s['base']/n:.6f} joint_ll:{s['joint']/n:.6f} delta_ll:{d:.6f} se:{se:.6f} z:{z:.2f}"

def build_profile(conn,cutoff):
 q='''with b as (
 select r.venue_id,e.lane,w.wave_height_cm,case when re.finish_position=1 then 1 else 0 end win
 from v2_races r join v2_race_entries e using(race_id)
 join v2_result_entries re on re.race_id=e.race_id and re.lane=e.lane
 join v2_realtime_weather_snapshots w on w.race_id=r.race_id and w.snapshot_label=%s
 where r.race_date between %s and %s and re.finish_position between 1 and 6 and w.wave_height_cm is not null)
 select venue_id,lane,
 case when wave_height_cm<3 then '<3' when wave_height_cm<6 then '3-<6' when wave_height_cm<10 then '6-<10' else '10+' end bucket,
 count(*) n,sum(win) wins
 from b group by venue_id,lane,3'''
 with conn.cursor() as c:
  c.execute(q,(HIST,START,cutoff)); rows=[dict(x) for x in c.fetchall()]
 base=defaultdict(lambda:[0,0]);
 for x in rows:base[(str(x['venue_id']).zfill(2),int(x['lane']))][0]+=int(x['n']);base[(str(x['venue_id']).zfill(2),int(x['lane']))][1]+=int(x['wins'])
 out={}
 for x in rows:
  v=str(x['venue_id']).zfill(2);l=int(x['lane']);n=int(x['n']);wins=int(x['wins']);bn,bw=base[(v,l)]
  if n<MIN_BUCKET or bn<MIN_BASE:continue
  pb=(wins+.5)/(n+1.);p0=(bw+.5)/(bn+1.);out[(v,l,str(x['bucket']))]=(logit(pb)-logit(p0))*(n/(n+SHRINK_K))
 return out

def rows_for_month(conn,a,b):
 with conn.cursor() as c:
  c.execute("set statement_timeout='180s'")
  c.execute('select race_id,race_date,coalesce(venue_id,venue_code) venue_id from v2_races where race_date>=%s and race_date<%s order by race_id',(a,b));races=[dict(x) for x in c.fetchall()]
  c.execute('''select e.race_id,e.lane,e.motor_place2_rate from v2_race_entries e join v2_races r using(race_id) where r.race_date>=%s and r.race_date<%s order by e.race_id,e.lane''',(a,b));er=[dict(x) for x in c.fetchall()]
  c.execute('''select x.race_id,x.lane,x.exhibition_time_rank from v2_realtime_exhibition_snapshots x join v2_races r using(race_id) where r.race_date>=%s and r.race_date<%s and x.snapshot_label=%s order by x.race_id,x.lane''',(a,b,HIST));xr=[dict(x) for x in c.fetchall()]
  c.execute('''select w.race_id,w.wave_height_cm from v2_realtime_weather_snapshots w join v2_races r using(race_id) where r.race_date>=%s and r.race_date<%s and w.snapshot_label=%s''',(a,b,HIST));wr={str(x['race_id']):sf(x['wave_height_cm']) for x in c.fetchall()}
  c.execute('''select o.race_id,o.ticket,o.odds from v2_odds_trifecta o join v2_races r using(race_id) where r.race_date>=%s and r.race_date<%s and o.odds>1 order by o.race_id,o.ticket''',(a,b));oo=[dict(x) for x in c.fetchall()]
  c.execute('''select res.race_id,res.trifecta_ticket from v2_results res join v2_races r using(race_id) where r.race_date>=%s and r.race_date<%s''',(a,b));rr={str(x['race_id']):nt(x['trifecta_ticket']) for x in c.fetchall()}
 eb=defaultdict(list);xb=defaultdict(list);ob=defaultdict(dict)
 for x in er:eb[str(x['race_id'])].append(x)
 for x in xr:xb[str(x['race_id'])].append(x)
 for x in oo:
  t=nt(x['ticket']);
  if t:ob[str(x['race_id'])][t]=float(x['odds'])
 return races,eb,xb,wr,ob,rr

def main():
 if not DB:raise RuntimeError('DATABASE_URL is required')
 print('BAO_WAVE_OOS_MODE=read_only',flush=True);print('BAO_WAVE_OOS_BASELINE=devig_market_plus_motor2_plus_exhibition',flush=True)
 splitstats=[];months=defaultdict(stat_new);overall=stat_new();selected=[]
 with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
  for si,(cut,ta,tb,bm,bx) in enumerate(SPLITS,1):
   prof=build_profile(conn,cut); losses={w:0. for w in WGRID};ln=0; test=stat_new(); print(f'BAO_WAVE_PROFILE=split:{si} groups:{len(prof)} train_end:{cut}',flush=True)
   cur=date(START.year,START.month,1)
   while cur<=tb:
    mx=nextm(cur);a=max(cur,START);b=min(mx,tb+timedelta(days=1));races,eb,xb,wr,ob,rr=rows_for_month(conn,a,b)
    for r in races:
     d=r['race_date'];rid=str(r['race_id']);actual=rr.get(rid,'');wave=wr.get(rid);om=ob.get(rid,{});sc=entry_scores(eb.get(rid,[]),xb.get(rid,[]))
     if wave is None or sc is None or len(om)!=120 or actual not in om:continue
     inv={t:1./o for t,o in om.items() if o>1};
     if len(inv)!=120:continue
     q={t:v/sum(inv.values()) for t,v in inv.items()};sm,sx=sc;sw=wave_score(prof,str(r.get('venue_id') or '').zfill(2),wb(wave));base=adj(q,sm,sx,sw,bm,bx,0.)
     if d<=cut:
      for w in WGRID:losses[w]+=-math.log(max(adj(q,sm,sx,sw,bm,bx,w)[actual],EPS))
      ln+=1
     elif ta<=d<=tb:
      pass
    cur=mx
   best=min(WGRID,key=lambda w:losses[w]/max(ln,1));selected.append(best);print(f'BAO_WAVE_SELECT=split:{si} weight:{best:.2f} train_n:{ln} top:'+','.join(f'{w:.2f}:{losses[w]/max(ln,1):.6f}' for w in sorted(WGRID,key=lambda x:losses[x])[:4]),flush=True)
   cur=date(ta.year,ta.month,1)
   while cur<=tb:
    mx=nextm(cur);a=max(cur,ta);b=min(mx,tb+timedelta(days=1));races,eb,xb,wr,ob,rr=rows_for_month(conn,a,b)
    for r in races:
     rid=str(r['race_id']);actual=rr.get(rid,'');wave=wr.get(rid);om=ob.get(rid,{});sc=entry_scores(eb.get(rid,[]),xb.get(rid,[]))
     if wave is None or sc is None or len(om)!=120 or actual not in om:continue
     inv={t:1./o for t,o in om.items() if o>1};
     if len(inv)!=120:continue
     q={t:v/sum(inv.values()) for t,v in inv.items()};sm,sx=sc;sw=wave_score(prof,str(r.get('venue_id') or '').zfill(2),wb(wave));base=adj(q,sm,sx,sw,bm,bx,0.);joint=adj(q,sm,sx,sw,bm,bx,best);stat_add(test,base,joint,actual);stat_add(months[r['race_date'].strftime('%Y-%m')],base,joint,actual)
    cur=mx
   splitstats.append(test);merge(overall,test);print(f'BAO_WAVE_SPLIT={si} test:{ta}..{tb} motor:{bm:.2f} exhibition:{bx:.2f} wave:{best:.2f} {fmt(test)}',flush=True)
 print('BAO_WAVE_SELECTED_WEIGHTS='+','.join(f'{x:.2f}' for x in selected),flush=True)
 neg=0
 for m in sorted(months):
  s=months[m];neg+=int(s['ds']/s['n']<0);print(f'BAO_WAVE_MONTH={m} {fmt(s)}',flush=True)
 print(f'BAO_WAVE_MONTH_STABILITY=negative:{neg}/{len(months)}',flush=True);print('BAO_WAVE_ALL='+fmt(overall),flush=True)
 n=overall['n'];d=overall['ds']/n if n else 0.;var=max(0.,(overall['d2']-overall['ds']**2/n)/(n-1)) if n>1 else 0.;se=math.sqrt(var/n) if n else 0.;robust=n>0 and d<0 and all(w>0 for w in selected) and neg>=6 and (se==0 or d/se<=-2)
 print('BAO_WAVE_VERDICT='+('ROBUST_CANDIDATE' if robust else 'NOT_YET_ROBUST'),flush=True);print('BAO_WAVE_POLICY=no_production_change',flush=True);print('BAO_WAVE_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__':main()
