# -*- coding: utf-8 -*-
"""Read-only readiness audit for weather residual modeling beyond market+Motor2+exhibition."""
from __future__ import annotations
import os
from datetime import date
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip(); START=date(2025,7,1); END=date(2026,8,22); HIST='historical'

def one(c,q,p=()):
    c.execute(q,p); return dict(c.fetchone() or {})

def main():
    if not DB: raise RuntimeError('DATABASE_URL is required')
    print(f'BAO_WX_READY_MODE=read_only period:{START}..{END}',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute("set statement_timeout='180s'")
            q='''
            with races as (
              select race_id,race_date from v2_races where race_date between %s and %s
            ),
            e as (
              select e.race_id,
                     count(*) filter(where e.motor_place2_rate between 0 and 100) motor_n
              from v2_race_entries e join races r using(race_id) group by e.race_id
            ),
            x as (
              select x.race_id,
                     count(*) filter(where x.exhibition_time_rank between 1 and 6) ex_n
              from v2_realtime_exhibition_snapshots x join races r using(race_id)
              where x.snapshot_label=%s group by x.race_id
            ),
            w as (
              select w.race_id,
                     max(w.wave_height_cm) wave_height_cm,
                     max(w.wind_speed_m) wind_speed_m
              from v2_realtime_weather_snapshots w join races r using(race_id)
              where w.snapshot_label=%s group by w.race_id
            ),
            o as (
              select o.race_id,count(distinct o.ticket) odds_n
              from v2_odds_trifecta o join races r using(race_id)
              where o.odds>1 group by o.race_id
            ),
            z as (
              select r.race_id,r.race_date,
                     coalesce(e.motor_n,0) motor_n,coalesce(x.ex_n,0) ex_n,coalesce(o.odds_n,0) odds_n,
                     w.wave_height_cm,w.wind_speed_m
              from races r left join e using(race_id) left join x using(race_id) left join w using(race_id) left join o using(race_id)
            )
            select to_char(race_date,'YYYY-MM') as month_key,count(*) as races,
              count(*) filter(where motor_n=6) as motor6,
              count(*) filter(where ex_n=6) as ex6,
              count(*) filter(where odds_n=120) as odds120,
              count(*) filter(where wave_height_cm is not null) as wave,
              count(*) filter(where wind_speed_m is not null) as wind,
              count(*) filter(where motor_n=6 and ex_n=6 and odds_n=120 and wave_height_cm is not null) as joint_wave,
              count(*) filter(where motor_n=6 and ex_n=6 and odds_n=120 and wind_speed_m is not null) as joint_wind
            from z group by 1 order by 1
            '''
            c.execute(q,(START,END,HIST,HIST)); rows=[dict(x) for x in c.fetchall()]
            total={'races':0,'joint_wave':0,'joint_wind':0}
            for r in rows:
                print('BAO_WX_READY_MONTH='+ ' '.join(f'{k}:{v}' for k,v in r.items()),flush=True)
                total['races']+=int(r['races']); total['joint_wave']+=int(r['joint_wave']); total['joint_wind']+=int(r['joint_wind'])
            dist=one(c,'''select count(*) as rows,
                count(*) filter(where wave_height_cm<3) as wave_lt3,
                count(*) filter(where wave_height_cm>=3 and wave_height_cm<6) as wave_3_6,
                count(*) filter(where wave_height_cm>=6 and wave_height_cm<10) as wave_6_10,
                count(*) filter(where wave_height_cm>=10) as wave_ge10,
                count(*) filter(where wind_speed_m<2) as wind_lt2,
                count(*) filter(where wind_speed_m>=2 and wind_speed_m<4) as wind_2_4,
                count(*) filter(where wind_speed_m>=4 and wind_speed_m<6) as wind_4_6,
                count(*) filter(where wind_speed_m>=6) as wind_ge6
                from v2_realtime_weather_snapshots w join v2_races r using(race_id)
                where r.race_date between %s and %s and w.snapshot_label=%s''',(START,END,HIST))
    print('BAO_WX_READY_TOTAL='+ ' '.join(f'{k}:{v}' for k,v in total.items()),flush=True)
    print('BAO_WX_READY_DIST='+ ' '.join(f'{k}:{v}' for k,v in dist.items()),flush=True)
    enough=total['joint_wave']>=10000 and total['joint_wind']>=10000
    print('BAO_WX_READY_VERDICT='+('READY_FOR_RESIDUAL_OOS' if enough else 'INSUFFICIENT_FOR_RESIDUAL_OOS'),flush=True)
    print('BAO_WX_READY_POLICY=read_only_no_production_change',flush=True)
    print('BAO_WX_READY_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__': main()
