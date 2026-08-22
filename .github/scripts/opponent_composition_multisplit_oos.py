# -*- coding: utf-8 -*-
"""Read-only multi-split OOS audit for opponent composition effects.

Measures whether racer x own-lane x opponent-lane/class effects persist OOS
relative to the racer's own-lane baseline. Also reports a global class/lane
reference. No DB writes, coefficients, Production, Shadow, or LINE changes.
"""
from __future__ import annotations
from datetime import date
import os
import psycopg
from psycopg.rows import dict_row

DB=os.environ.get('DATABASE_URL','').strip()
START=date(2025,7,1); END=date(2026,8,22)
SPLITS=(date(2026,3,31),date(2026,4,30),date(2026,5,31))
GATES=(('MODERATE',15,6,30,12,20.0,0.020,0.030),('STRICT',25,10,45,18,30.0,0.020,0.030))

def one(conn,q,p=()):
    with conn.cursor() as c:
        c.execute(q,p); r=c.fetchone(); return dict(r) if r else {}

def pct(a,b): return 0.0 if not b else 100.0*a/b

def audit_individual(conn,split,tn,on,bn,bo,shrink_k,win_min,top3_min):
    q="""
    with base as (
      select r.race_date,a.racer_number,a.lane own_lane,b.lane opp_lane,b.racer_class opp_class,
             case when re.finish_position=1 then 1.0 else 0.0 end win,
             case when re.finish_position between 1 and 3 then 1.0 else 0.0 end top3
      from v2_race_entries a
      join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
      join v2_races r on r.race_id=a.race_id
      join v2_result_entries re on re.race_id=a.race_id and re.lane=a.lane
      where r.race_date between %s and %s and a.racer_number is not null
        and a.lane between 1 and 6 and b.lane between 1 and 6
        and b.racer_class between 1 and 4 and re.finish_position between 1 and 6
    ),
    tc as (select racer_number,own_lane,opp_lane,opp_class,count(*) n,avg(win) wr,avg(top3) tr from base where race_date<=%s group by 1,2,3,4),
    tb as (select racer_number,own_lane,count(distinct race_date::text||'|'||opp_lane::text||'|'||opp_class::text) dummy,count(*)/5.0 n,avg(win) wr,avg(top3) tr from base where race_date<=%s group by 1,2),
    oc as (select racer_number,own_lane,opp_lane,opp_class,count(*) n,avg(win) wr,avg(top3) tr from base where race_date>%s group by 1,2,3,4),
    ob as (select racer_number,own_lane,count(*)/5.0 n,avg(win) wr,avg(top3) tr from base where race_date>%s group by 1,2),
    m as (
      select tc.n tn,oc.n onum,(tc.wr-tb.wr) tw,(oc.wr-ob.wr) ow,(tc.tr-tb.tr) tt,(oc.tr-ob.tr) ot,
             tc.n::float8/(tc.n+%s) shrink
      from tc join oc using(racer_number,own_lane,opp_lane,opp_class)
      join tb using(racer_number,own_lane) join ob using(racer_number,own_lane)
      where tc.n>=%s and oc.n>=%s and tb.n>=%s and ob.n>=%s
    )
    select count(*)::bigint matched,
      count(*) filter(where abs(tw*shrink)>=%s)::bigint win_meaningful,
      count(*) filter(where abs(tw*shrink)>=%s and tw*ow>0)::bigint win_agree,
      count(*) filter(where abs(tt*shrink)>=%s)::bigint top3_meaningful,
      count(*) filter(where abs(tt*shrink)>=%s and tt*ot>0)::bigint top3_agree,
      coalesce(avg(abs(tw*shrink)),0)::float8 win_abs,coalesce(avg(abs(tt*shrink)),0)::float8 top3_abs
    from m
    """
    return one(conn,q,(START,END,split,split,split,split,shrink_k,tn,on,bn,bo,win_min,win_min,top3_min,top3_min))

def audit_global(conn,split):
    q="""
    with base as (
      select r.race_date,a.racer_class own_class,a.lane own_lane,b.lane opp_lane,b.racer_class opp_class,
             case when re.finish_position=1 then 1.0 else 0.0 end win,
             case when re.finish_position between 1 and 3 then 1.0 else 0.0 end top3
      from v2_race_entries a join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
      join v2_races r on r.race_id=a.race_id
      join v2_result_entries re on re.race_id=a.race_id and re.lane=a.lane
      where r.race_date between %s and %s and a.racer_class between 1 and 4 and b.racer_class between 1 and 4
        and re.finish_position between 1 and 6
    ),
    tc as (select own_class,own_lane,opp_lane,opp_class,count(*) n,avg(win) wr,avg(top3) tr from base where race_date<=%s group by 1,2,3,4),
    tb as (select own_class,own_lane,count(*)/5.0 n,avg(win) wr,avg(top3) tr from base where race_date<=%s group by 1,2),
    oc as (select own_class,own_lane,opp_lane,opp_class,count(*) n,avg(win) wr,avg(top3) tr from base where race_date>%s group by 1,2,3,4),
    ob as (select own_class,own_lane,count(*)/5.0 n,avg(win) wr,avg(top3) tr from base where race_date>%s group by 1,2),
    m as (
      select (tc.wr-tb.wr) tw,(oc.wr-ob.wr) ow,(tc.tr-tb.tr) tt,(oc.tr-ob.tr) ot
      from tc join oc using(own_class,own_lane,opp_lane,opp_class)
      join tb using(own_class,own_lane) join ob using(own_class,own_lane)
      where tc.n>=100 and oc.n>=40 and tb.n>=500 and ob.n>=150
    )
    select count(*)::bigint matched,
      count(*) filter(where abs(tw)>=.01)::bigint win_meaningful,count(*) filter(where abs(tw)>=.01 and tw*ow>0)::bigint win_agree,
      count(*) filter(where abs(tt)>=.015)::bigint top3_meaningful,count(*) filter(where abs(tt)>=.015 and tt*ot>0)::bigint top3_agree
    from m
    """
    return one(conn,q,(START,END,split,split,split,split))

def main():
    if not DB: raise RuntimeError('DATABASE_URL required')
    print('OPPONENT_OOS_MODE=read_only',flush=True)
    print(f'OPPONENT_OOS_PERIOD={START}..{END}',flush=True)
    print('OPPONENT_OOS_CLASS_MAP=B2:1 B1:2 A2:3 A1:4',flush=True)
    print('OPPONENT_OOS_POLICY=delta_vs_own_racer_lane_baseline_no_coefficients_no_writes',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
      with conn.cursor() as c:
        c.execute('set max_parallel_workers_per_gather=0'); c.execute("set work_mem='8MB'"); c.execute("set statement_timeout='180s'")
      for split in SPLITS:
        print(f'OPPONENT_OOS_SPLIT={split}',flush=True)
        g=audit_global(conn,split)
        wm=int(g.get('win_meaningful') or 0); wa=int(g.get('win_agree') or 0); tm=int(g.get('top3_meaningful') or 0); ta=int(g.get('top3_agree') or 0)
        print(f"OPPONENT_OOS_GLOBAL=matched:{int(g.get('matched') or 0)} win:{wa}/{wm}({pct(wa,wm):.1f}%) top3:{ta}/{tm}({pct(ta,tm):.1f}%)",flush=True)
        for name,tn,on,bn,bo,k,wmin,tmin in GATES:
          r=audit_individual(conn,split,tn,on,bn,bo,k,wmin,tmin)
          wm=int(r.get('win_meaningful') or 0); wa=int(r.get('win_agree') or 0); tm=int(r.get('top3_meaningful') or 0); ta=int(r.get('top3_agree') or 0)
          print(f"OPPONENT_OOS_{name}=matched:{int(r.get('matched') or 0)} win:{wa}/{wm}({pct(wa,wm):.1f}%) top3:{ta}/{tm}({pct(ta,tm):.1f}%) mean_abs_win_pt:{100*float(r.get('win_abs') or 0):.2f} mean_abs_top3_pt:{100*float(r.get('top3_abs') or 0):.2f}",flush=True)
    print('OPPONENT_OOS_RESULT=PASS_READ_ONLY',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc:
      print(f"OPPONENT_OOS_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}",flush=True); raise
