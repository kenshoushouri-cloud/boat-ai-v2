# -*- coding: utf-8 -*-
"""Read-only readiness audit for wind-direction residual modeling.

Checks historical coverage of official relative wind-direction labels and whether
those labels coexist with the current Bao baseline inputs: full trifecta odds,
Motor2 entry data, and exhibition-time ranks. No DB writes.
"""
from __future__ import annotations
import os
from datetime import date
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip(); START=date(2025,7,1); END=date(2026,8,22); HIST='historical'
RELATIVE=('向い風','追い風','右横風','左横風')

def main():
    if not DB: raise RuntimeError('DATABASE_URL is required')
    print(f'BAO_WDIR_READY_MODE=read_only period:{START}..{END}',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute("set statement_timeout='180s'")
            c.execute('''
            with races as (
              select race_id,race_date from v2_races where race_date between %s and %s
            ), e as (
              select e.race_id,count(*) filter(where e.motor_place2_rate between 0 and 100) motor_n
              from v2_race_entries e join races r using(race_id) group by e.race_id
            ), x as (
              select x.race_id,count(*) filter(where x.exhibition_time_rank between 1 and 6) ex_n
              from v2_realtime_exhibition_snapshots x join races r using(race_id)
              where x.snapshot_label=%s group by x.race_id
            ), o as (
              select o.race_id,count(distinct o.ticket) odds_n
              from v2_odds_trifecta o join races r using(race_id) where o.odds>1 group by o.race_id
            ), w as (
              select w.race_id,max(w.wind_direction) wind_direction
              from v2_realtime_weather_snapshots w join races r using(race_id)
              where w.snapshot_label=%s group by w.race_id
            ), z as (
              select r.race_id,r.race_date,coalesce(e.motor_n,0) motor_n,coalesce(x.ex_n,0) ex_n,
                     coalesce(o.odds_n,0) odds_n,w.wind_direction
              from races r left join e using(race_id) left join x using(race_id)
              left join o using(race_id) left join w using(race_id)
            )
            select to_char(race_date,'YYYY-MM') month_key,count(*) races,
                   count(*) filter(where wind_direction is not null and wind_direction<>'') dir_any,
                   count(*) filter(where wind_direction in ('向い風','追い風','右横風','左横風')) dir_relative,
                   count(*) filter(where motor_n=6 and ex_n=6 and odds_n=120 and wind_direction is not null and wind_direction<>'') joint_any,
                   count(*) filter(where motor_n=6 and ex_n=6 and odds_n=120 and wind_direction in ('向い風','追い風','右横風','左横風')) joint_relative
            from z group by 1 order by 1
            ''',(START,END,HIST,HIST)); rows=[dict(x) for x in c.fetchall()]
            totals={'races':0,'dir_any':0,'dir_relative':0,'joint_any':0,'joint_relative':0}
            for r in rows:
                print('BAO_WDIR_READY_MONTH='+' '.join(f'{k}:{v}' for k,v in r.items()),flush=True)
                for k in totals: totals[k]+=int(r[k])
            c.execute('''select coalesce(nullif(trim(wind_direction),''),'NULL') label,count(*) n
                         from v2_realtime_weather_snapshots w join v2_races r using(race_id)
                         where r.race_date between %s and %s and w.snapshot_label=%s
                         group by 1 order by count(*) desc,1''',(START,END,HIST)); dist=[dict(x) for x in c.fetchall()]
    print('BAO_WDIR_READY_TOTAL='+' '.join(f'{k}:{v}' for k,v in totals.items()),flush=True)
    for r in dist[:20]: print(f"BAO_WDIR_READY_DIST=label:{r['label']} n:{r['n']}",flush=True)
    enough=totals['joint_relative']>=10000
    print('BAO_WDIR_READY_VERDICT='+('READY_FOR_RELATIVE_DIRECTION_OOS' if enough else 'RELATIVE_DIRECTION_COVERAGE_INSUFFICIENT'),flush=True)
    print('BAO_WDIR_READY_POLICY=read_only_no_production_change',flush=True)
    print('BAO_WDIR_READY_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__': main()
