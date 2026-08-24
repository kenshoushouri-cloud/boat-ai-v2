# -*- coding: utf-8 -*-
"""Read-only OOS stratification of fixed Opponent Pressure by meet-day x race band.

Uses the established fixed design: train-only own_class x own_lane x opponent_lane x
opponent_class effects, SHRINK_K=100, conditional support>=40, baseline support>=500.
Adds no tuning: only fixed D1/D2/D3-4/D5+ and R01-04/R05-08/R09-12 diagnostics.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import math
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip()
START=date(2025,7,1); BUFFER=date(2025,6,24); END=date(2026,8,24)
SPLITS=(date(2026,3,31),date(2026,4,30),date(2026,5,31))
SHRINK_K=100.0; TRAIN_COND_MIN=40; TRAIN_BASE_MIN=500; MAX_MEET_DAYS=7; EPS=1e-12


def dbucket(d:int)->str:
    if d==1:return 'D1'
    if d==2:return 'D2'
    if d in (3,4):return 'D3_4'
    return 'D5_PLUS'

def rband(r:int)->str:
    return 'R01_04' if r<=4 else ('R05_08' if r<=8 else 'R09_12')

def infer_days(rows:list[dict[str,Any]])->dict[tuple[str,date],int]:
    vd:dict[str,list[date]]=defaultdict(list)
    for r in rows: vd[r['venue']].append(r['race_date'])
    out={}
    for v,ds0 in vd.items():
        ds=sorted(set(ds0)); streak=[]; streaks=[]
        for d in ds:
            if not streak or d==streak[-1]+timedelta(days=1): streak.append(d)
            else: streaks.append(streak); streak=[d]
        if streak: streaks.append(streak)
        for s in streaks:
            if len(s)<=MAX_MEET_DAYS:
                for i,d in enumerate(s,1): out[(v,d)]=i
    return out

def metric(rows:list[dict[str,Any]])->tuple[int,float,float,float,float]:
    if not rows:return 0,0,0,0,0
    n=len(rows)
    wb=sum((float(r['win'])-float(r['pwin']))**2 for r in rows)/n
    wa=sum((float(r['win'])-float(r['pwin_adj']))**2 for r in rows)/n
    winners=[r for r in rows if float(r['win'])==1.0]
    lb=sum(-math.log(max(EPS,float(r['pwin_norm_base']))) for r in winners)/len(winners)
    la=sum(-math.log(max(EPS,float(r['pwin_norm_adj']))) for r in winners)/len(winners)
    return len(winners),wb,wa,lb,la

def load_venue_dates(conn)->list[dict[str,Any]]:
    with conn.cursor() as cur:
        cur.execute("""select distinct race_date::date race_date,
          lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0') venue
          from v2_races where race_date between %s and %s and race_no between 1 and 12""",(BUFFER,END))
        return [dict(x) for x in cur.fetchall()]

def scored(conn,split:date)->list[dict[str,Any]]:
    q="""
    with base as (
      select r.race_date::date race_date,r.race_id,
             lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') venue,
             r.race_no::int race_no,a.lane own_lane,a.racer_class own_class,
             b.lane opp_lane,b.racer_class opp_class,
             case when re.finish_position=1 then 1.0 else 0.0 end win
      from v2_race_entries a join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
      join v2_races r on r.race_id=a.race_id
      join v2_result_entries re on re.race_id=a.race_id and re.lane=a.lane
      where r.race_date between %s and %s and a.racer_class between 1 and 4
        and b.racer_class between 1 and 4 and re.finish_position between 1 and 6
    ), tbase as (
      select own_class,own_lane,count(*)/5.0 n,avg(win) pwin
      from base where race_date<=%s group by 1,2
    ), teff as (
      select b.own_class,b.own_lane,b.opp_lane,b.opp_class,count(*) n,
             (avg(b.win)-tb.pwin)*(count(*)::float8/(count(*)+%s)) ewin
      from base b join tbase tb using(own_class,own_lane)
      where b.race_date<=%s and tb.n>=%s
      group by b.own_class,b.own_lane,b.opp_lane,b.opp_class,tb.pwin
      having count(*)>=%s
    ), s as (
      select b.race_id,b.race_date,b.venue,b.race_no,b.own_lane,max(b.win) win,tb.pwin,
             avg(coalesce(t.ewin,0)) score,count(t.opp_lane) matched
      from base b join tbase tb using(own_class,own_lane)
      left join teff t using(own_class,own_lane,opp_lane,opp_class)
      where b.race_date>%s and tb.n>=%s
      group by b.race_id,b.race_date,b.venue,b.race_no,b.own_lane,tb.pwin
    ), p as (
      select *,greatest(.001,least(.999,pwin+score)) pwin_adj from s where matched>=4
    ), six as (
      select *,count(*) over(partition by race_id) lanes from p
    )
    select *,greatest(.001,pwin)/sum(greatest(.001,pwin)) over(partition by race_id) pwin_norm_base,
             greatest(.001,pwin_adj)/sum(greatest(.001,pwin_adj)) over(partition by race_id) pwin_norm_adj
    from six where lanes=6 order by race_date,race_id,own_lane
    """
    params=(START,END,split,SHRINK_K,split,TRAIN_BASE_MIN,TRAIN_COND_MIN,split,TRAIN_BASE_MIN)
    with conn.cursor() as cur:
        cur.execute(q,params); return [dict(x) for x in cur.fetchall()]

def main()->None:
    if not DB: raise RuntimeError('DATABASE_URL required')
    print('OPP_MEET_RACE_MODE=read_only_fixed_oos_stratification_no_tuning',flush=True)
    print('OPP_MEET_RACE_POLICY=no_writes_no_production_no_line_no_threshold_search_no_coefficient_tuning',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute('set max_parallel_workers_per_gather=0'); cur.execute("set work_mem='8MB'"); cur.execute("set statement_timeout='300s'")
        daymap=infer_days(load_venue_dates(conn))
        aggregate:dict[tuple[str,str],list[tuple[float,float]]]=defaultdict(list)
        for split in SPLITS:
            rows=scored(conn,split)
            for r in rows:
                d=daymap.get((r['venue'],r['race_date']))
                r['day_bucket']=dbucket(d) if d else 'AMBIG'; r['race_band']=rband(r['race_no'])
            rows=[r for r in rows if r['day_bucket']!='AMBIG']
            for db in ('D1','D2','D3_4','D5_PLUS'):
                for rb in ('R01_04','R05_08','R09_12'):
                    sub=[r for r in rows if r['day_bucket']==db and r['race_band']==rb]
                    nr,wb,wa,lb,la=metric(sub); aggregate[(db,rb)].append((wa-wb,la-lb))
                    print(f'OPP_MEET_RACE={split}|{db}|{rb} races:{nr} brier_delta:{wa-wb:+.8f} logloss_delta:{la-lb:+.8f}',flush=True)
        for (db,rb),vals in aggregate.items():
            bi=sum(x<0 for x,_ in vals); li=sum(y<0 for _,y in vals)
            print(f'OPP_MEET_RACE_STABILITY={db}|{rb} brier_improve:{bi}/3 logloss_improve:{li}/3',flush=True)
    print('OPP_MEET_RACE_INTERPRETATION=fixed_subgroup_stability_only_no_subgroup_selection',flush=True)
    print('OPP_MEET_RACE_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE',flush=True)
    print('OPP_MEET_RACE_RESULT=PASS_READ_ONLY',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(f'OPP_MEET_RACE_ERROR={type(exc).__name__}:{str(exc).replace(chr(10)," ")[:700]}',flush=True); raise
