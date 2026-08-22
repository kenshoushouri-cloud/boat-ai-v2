# -*- coding: utf-8 -*-
"""Read-only readiness audit for racer x own-lane x opponent-lane/class effects.
No DB writes, no Production/Shadow/LINE changes.
"""
from __future__ import annotations
import os
import psycopg
from psycopg.rows import dict_row

DB=os.environ.get('DATABASE_URL','').strip()
START=os.environ.get('OPPONENT_AUDIT_START','2025-07-01')
END=os.environ.get('OPPONENT_AUDIT_END','2026-08-22')

def one(conn,q,p=()):
    with conn.cursor() as c:
        c.execute(q,p); r=c.fetchone(); return dict(r) if r else {}

def main():
    if not DB: raise RuntimeError('DATABASE_URL required')
    print('OPPONENT_AUDIT_MODE=read_only',flush=True)
    print(f'OPPONENT_AUDIT_PERIOD={START}..{END}',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute('set max_parallel_workers_per_gather=0')
            c.execute("set work_mem='8MB'")
            c.execute("set statement_timeout='180s'")

        schema=one(conn,"""
          select count(*) filter(where column_name='racer_number') racer_number,
                 count(*) filter(where column_name='racer_class') racer_class,
                 count(*) filter(where column_name='lane') lane,
                 count(*) filter(where column_name='national_win_rate') national_win_rate
          from information_schema.columns
          where table_schema='public' and table_name='v2_race_entries'
        """)
        print('OPPONENT_SCHEMA='+' '.join(f'{k}:{int(v or 0)}' for k,v in schema.items()),flush=True)
        if not all(int(schema.get(k) or 0)==1 for k in ('racer_number','racer_class','lane')):
            raise SystemExit(2)

        base=one(conn,"""
          select count(*)::bigint participant_rows,
                 count(distinct e.racer_number)::bigint racers,
                 count(*) filter(where e.racer_class in ('A1','A2','B1','B2'))::bigint valid_class_rows
          from v2_race_entries e
          join v2_races r on r.race_id=e.race_id
          where r.race_date between %s and %s and e.racer_number is not null
        """,(START,END))
        print('OPPONENT_BASE='+' '.join(f'{k}:{int(v or 0)}' for k,v in base.items()),flush=True)

        pair=one(conn,"""
          with g as (
            select a.racer_number,a.lane own_lane,b.lane opp_lane,b.racer_class opp_class,count(*) n
            from v2_race_entries a join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
            join v2_races r on r.race_id=a.race_id
            where r.race_date between %s and %s and a.racer_number is not null
              and a.lane between 1 and 6 and b.lane between 1 and 6
              and b.racer_class in ('A1','A2','B1','B2') group by 1,2,3,4
          )
          select count(*)::bigint groups,count(*) filter(where n>=10)::bigint ge10,
                 count(*) filter(where n>=20)::bigint ge20,count(*) filter(where n>=30)::bigint ge30,
                 count(*) filter(where n>=50)::bigint ge50,
                 percentile_cont(.5) within group(order by n)::float8 median_n,
                 percentile_cont(.9) within group(order by n)::float8 p90_n,max(n)::bigint max_n from g
        """,(START,END))
        print('OPPONENT_PAIR_DENSITY='+' '.join(f'{k}:{v}' for k,v in pair.items()),flush=True)

        exact=one(conn,"""
          with x as (
            select e.race_id,e.racer_number,e.lane,
              max(case when o.lane=1 then o.racer_class end) c1,max(case when o.lane=2 then o.racer_class end) c2,
              max(case when o.lane=3 then o.racer_class end) c3,max(case when o.lane=4 then o.racer_class end) c4,
              max(case when o.lane=5 then o.racer_class end) c5,max(case when o.lane=6 then o.racer_class end) c6
            from v2_race_entries e join v2_race_entries o on o.race_id=e.race_id and o.lane<>e.lane
            join v2_races r on r.race_id=e.race_id
            where r.race_date between %s and %s and e.racer_number is not null and o.racer_class in ('A1','A2','B1','B2')
            group by 1,2,3
          ), g as (select racer_number,lane,c1,c2,c3,c4,c5,c6,count(*) n from x group by 1,2,3,4,5,6,7,8)
          select count(*)::bigint groups,count(*) filter(where n>=10)::bigint ge10,
                 count(*) filter(where n>=20)::bigint ge20,count(*) filter(where n>=30)::bigint ge30,
                 percentile_cont(.5) within group(order by n)::float8 median_n,max(n)::bigint max_n from g
        """,(START,END))
        print('OPPONENT_EXACT_PATTERN_DENSITY='+' '.join(f'{k}:{v}' for k,v in exact.items()),flush=True)

        agg=one(conn,"""
          with x as (
            select a.race_id,a.racer_number,a.lane,
              count(*) filter(where b.racer_class='A1') a1_n,count(*) filter(where b.racer_class='A2') a2_n,
              count(*) filter(where b.racer_class='B1') b1_n,count(*) filter(where b.racer_class='B2') b2_n,
              count(*) filter(where b.lane<a.lane and b.racer_class in ('A1','A2')) inner_a_n,
              count(*) filter(where b.lane>a.lane and b.racer_class in ('A1','A2')) outer_a_n
            from v2_race_entries a join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
            join v2_races r on r.race_id=a.race_id
            where r.race_date between %s and %s and a.racer_number is not null and b.racer_class in ('A1','A2','B1','B2')
            group by 1,2,3
          ), g as (
            select racer_number,lane,a1_n,a2_n,b1_n,b2_n,inner_a_n,outer_a_n,count(*) n
            from x group by 1,2,3,4,5,6,7,8)
          select count(*)::bigint groups,count(*) filter(where n>=10)::bigint ge10,
                 count(*) filter(where n>=20)::bigint ge20,count(*) filter(where n>=30)::bigint ge30,
                 count(*) filter(where n>=50)::bigint ge50,
                 percentile_cont(.5) within group(order by n)::float8 median_n,
                 percentile_cont(.9) within group(order by n)::float8 p90_n,max(n)::bigint max_n from g
        """,(START,END))
        print('OPPONENT_AGG_PATTERN_DENSITY='+' '.join(f'{k}:{v}' for k,v in agg.items()),flush=True)

        lane_class=one(conn,"""
          with g as (
            select a.lane own_lane,b.lane opp_lane,a.racer_class own_class,b.racer_class opp_class,count(*) n
            from v2_race_entries a join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
            join v2_races r on r.race_id=a.race_id
            where r.race_date between %s and %s and a.racer_class in ('A1','A2','B1','B2') and b.racer_class in ('A1','A2','B1','B2')
            group by 1,2,3,4)
          select count(*)::bigint groups,min(n)::bigint min_n,
                 percentile_cont(.5) within group(order by n)::float8 median_n,max(n)::bigint max_n from g
        """,(START,END))
        print('OPPONENT_CLASS_LANE_DENSITY='+' '.join(f'{k}:{v}' for k,v in lane_class.items()),flush=True)

    print('OPPONENT_AUDIT_RESULT=PASS_READ_ONLY',flush=True)
    print('OPPONENT_AUDIT_NEXT=multi_split_oos_for_supported_granularities',flush=True)

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        msg=str(exc).replace('\n',' ').replace('\r',' ')[:700]
        print(f'OPPONENT_AUDIT_ERROR={type(exc).__name__}:{msg}',flush=True)
        raise
