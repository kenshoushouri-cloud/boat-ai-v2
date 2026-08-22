# -*- coding: utf-8 -*-
"""Read-only audit of when complete 6-lane exhibition snapshots become available.

Uses realtime (non-historical) exhibition snapshots and compares snapshot_at with
v2_races.deadline_at. This determines whether exhibition-time rank can be used
in an early market model or must be introduced in a later update stage.
"""
from __future__ import annotations
import os
from datetime import date
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip(); START=date(2026,7,1); END=date(2026,8,22)

def main():
    if not DB: raise RuntimeError('DATABASE_URL is required')
    print(f'EX_TIMING_MODE=read_only period:{START}..{END}',flush=True)
    print('EX_TIMING_POLICY=nonhistorical_only_no_writes',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute("set statement_timeout='120s'")
            c.execute('''
              with g as (
                select x.race_id,x.snapshot_label,count(distinct x.lane) lanes,
                       max(x.snapshot_at) complete_at,r.deadline_at
                from v2_realtime_exhibition_snapshots x
                join v2_races r on r.race_id=x.race_id
                where r.race_date between %s and %s
                  and x.snapshot_label <> 'historical'
                  and x.snapshot_at is not null and r.deadline_at is not null
                group by x.race_id,x.snapshot_label,r.deadline_at
              ), z as (
                select *, extract(epoch from (deadline_at-complete_at))/60.0 mb
                from g where lanes=6
              )
              select snapshot_label,count(*)::bigint races,
                     min(complete_at) first_at,max(complete_at) last_at,
                     avg(mb)::float8 avg_mb,
                     count(*) filter(where mb>=30)::bigint ge30,
                     count(*) filter(where mb>=20 and mb<30)::bigint m20_30,
                     count(*) filter(where mb>=15 and mb<20)::bigint m15_20,
                     count(*) filter(where mb>=10 and mb<15)::bigint m10_15,
                     count(*) filter(where mb>=5 and mb<10)::bigint m5_10,
                     count(*) filter(where mb>=0 and mb<5)::bigint m0_5,
                     count(*) filter(where mb<0)::bigint after_deadline
              from z group by snapshot_label order by races desc
            ''',(START,END))
            rows=[dict(x) for x in c.fetchall()]
            for r in rows:
                print('EX_TIMING_LABEL label:{snapshot_label} races:{races} avg_min_before:{avg_mb:.2f} ge30:{ge30} m20_30:{m20_30} m15_20:{m15_20} m10_15:{m10_15} m5_10:{m5_10} m0_5:{m0_5} after:{after_deadline}'.format(**r),flush=True)
            c.execute('''
              with g as (
                select x.race_id,count(distinct x.lane) lanes,max(x.snapshot_at) complete_at,r.deadline_at
                from v2_realtime_exhibition_snapshots x join v2_races r on r.race_id=x.race_id
                where r.race_date between %s and %s and x.snapshot_label<>'historical'
                  and x.snapshot_at is not null and r.deadline_at is not null
                group by x.race_id,r.deadline_at
              ), z as (
                select *,extract(epoch from (deadline_at-complete_at))/60.0 mb from g where lanes=6
              )
              select count(*)::bigint races,
                     count(*) filter(where mb>=20)::bigint ge20,
                     count(*) filter(where mb>=15)::bigint ge15,
                     count(*) filter(where mb>=10)::bigint ge10,
                     count(*) filter(where mb>=5)::bigint ge5,
                     count(*) filter(where mb>=0)::bigint before_deadline,
                     percentile_cont(0.5) within group(order by mb)::float8 median_mb,
                     percentile_cont(0.1) within group(order by mb)::float8 p10_mb,
                     percentile_cont(0.9) within group(order by mb)::float8 p90_mb
              from z
            ''',(START,END))
            r=dict(c.fetchone() or {})
            print('EX_TIMING_ANY_LABEL races:{races} ge20:{ge20} ge15:{ge15} ge10:{ge10} ge5:{ge5} before:{before_deadline} median_mb:{median_mb:.2f} p10:{p10_mb:.2f} p90:{p90_mb:.2f}'.format(**r),flush=True)
    print('EX_TIMING_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__':main()
