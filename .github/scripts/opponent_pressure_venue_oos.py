# -*- coding: utf-8 -*-
"""Read-only chronological OOS venue stability audit for fixed Opponent Pressure.

Uses the established fixed design from opponent_pressure_meet_race_strata_oos.py:
train-only own_class x own_lane x opponent_lane x opponent_class effects,
SHRINK_K=100, conditional support>=40, baseline support>=500.
No tuning, writes, Production/LINE changes, or promotion.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
import math, os
from typing import Any
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip()
START=date(2025,7,1); END=date(2026,8,24)
SPLITS=(date(2026,3,31),date(2026,4,30),date(2026,5,31))
SHRINK_K=100.0; TRAIN_COND_MIN=40; TRAIN_BASE_MIN=500; EPS=1e-12
VENUES={f'{i:02d}' for i in range(1,25)}

def metric(rows:list[dict[str,Any]])->tuple[int,float,float,float,float]:
    if not rows:return 0,0,0,0,0
    n=len(rows)
    wb=sum((float(r['win'])-float(r['pwin']))**2 for r in rows)/n
    wa=sum((float(r['win'])-float(r['pwin_adj']))**2 for r in rows)/n
    winners=[r for r in rows if float(r['win'])==1.0]
    lb=sum(-math.log(max(EPS,float(r['pwin_norm_base']))) for r in winners)/len(winners)
    la=sum(-math.log(max(EPS,float(r['pwin_norm_adj']))) for r in winners)/len(winners)
    return len(winners),wb,wa,lb,la

def scored(conn,split:date)->list[dict[str,Any]]:
    q='''
    with base as (
      select r.race_date::date race_date,r.race_id,
             lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') venue,
             a.lane own_lane,a.racer_class own_class,b.lane opp_lane,b.racer_class opp_class,
             case when re.finish_position=1 then 1.0 else 0.0 end win
      from v2_race_entries a join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
      join v2_races r on r.race_id=a.race_id
      join v2_result_entries re on re.race_id=a.race_id and re.lane=a.lane
      where r.race_date between %s and %s and r.race_no between 1 and 12
        and a.racer_class between 1 and 4 and b.racer_class between 1 and 4
        and re.finish_position between 1 and 6
    ), tbase as (
      select own_class,own_lane,count(*)/5.0 n,avg(win) pwin from base where race_date<=%s group by 1,2
    ), teff as (
      select b.own_class,b.own_lane,b.opp_lane,b.opp_class,count(*) n,
             (avg(b.win)-tb.pwin)*(count(*)::float8/(count(*)+%s)) ewin
      from base b join tbase tb using(own_class,own_lane)
      where b.race_date<=%s and tb.n>=%s
      group by b.own_class,b.own_lane,b.opp_lane,b.opp_class,tb.pwin having count(*)>=%s
    ), s as (
      select b.race_id,b.race_date,b.venue,b.own_lane,max(b.win) win,tb.pwin,
             avg(coalesce(t.ewin,0)) score,count(t.opp_lane) matched
      from base b join tbase tb using(own_class,own_lane)
      left join teff t using(own_class,own_lane,opp_lane,opp_class)
      where b.race_date>%s and tb.n>=%s
      group by b.race_id,b.race_date,b.venue,b.own_lane,tb.pwin
    ), p as (
      select *,greatest(.001,least(.999,pwin+score)) pwin_adj from s where matched>=4
    ), six as (
      select *,count(*) over(partition by race_id) lanes from p
    )
    select *,greatest(.001,pwin)/sum(greatest(.001,pwin)) over(partition by race_id) pwin_norm_base,
             greatest(.001,pwin_adj)/sum(greatest(.001,pwin_adj)) over(partition by race_id) pwin_norm_adj
    from six where lanes=6 order by race_date,race_id,own_lane
    '''
    params=(START,END,split,SHRINK_K,split,TRAIN_BASE_MIN,TRAIN_COND_MIN,split,TRAIN_BASE_MIN)
    with conn.cursor() as cur:
        cur.execute(q,params); return [dict(x) for x in cur.fetchall()]

def main()->None:
    if not DB: raise RuntimeError('DATABASE_URL required')
    print('OPP_VENUE_OOS_MODE=read_only_fixed_oos_venue_stability_no_tuning',flush=True)
    print('OPP_VENUE_OOS_POLICY=no_writes_no_production_no_line_no_threshold_search_no_coefficient_tuning',flush=True)
    aggregate:dict[str,list[tuple[float,float,int]]]=defaultdict(list)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
      with conn.cursor() as cur:
        cur.execute('set max_parallel_workers_per_gather=0'); cur.execute("set work_mem='8MB'"); cur.execute("set statement_timeout='300s'")
      for split in SPLITS:
        rows=scored(conn,split)
        for v in sorted(VENUES):
          sub=[r for r in rows if r['venue']==v]
          nr,wb,wa,lb,la=metric(sub)
          aggregate[v].append((wa-wb,la-lb,nr))
          print(f'OPP_VENUE_OOS={split}|V{v} races:{nr} brier_delta:{wa-wb:+.8f} logloss_delta:{la-lb:+.8f}',flush=True)
    both3=brier3=ll3=both2=0
    for v in sorted(VENUES):
      vals=aggregate[v]; bi=sum(b<0 for b,_,_ in vals); li=sum(l<0 for _,l,_ in vals)
      brier3+=bi==3; ll3+=li==3; both3+=(bi==3 and li==3); both2+=(bi>=2 and li>=2)
      print(f'OPP_VENUE_OOS_STABILITY=V{v} brier_improve:{bi}/3 logloss_improve:{li}/3 races:{"/".join(str(n) for _,_,n in vals)}',flush=True)
    print(f'OPP_VENUE_OOS_SUMMARY=venues:24 brier_3of3:{brier3} logloss_3of3:{ll3} both_3of3:{both3} both_atleast_2of3:{both2}',flush=True)
    print('OPP_VENUE_OOS_INTERPRETATION=fixed_venue_stability_only_no_venue_selection',flush=True)
    print('OPP_VENUE_OOS_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE',flush=True)
    print('OPP_VENUE_OOS_RESULT=PASS_READ_ONLY',flush=True)

if __name__=='__main__':
  try: main()
  except Exception as exc:
    print(f'OPP_VENUE_OOS_ERROR={type(exc).__name__}:{str(exc).replace(chr(10)," ")[:700]}',flush=True); raise
