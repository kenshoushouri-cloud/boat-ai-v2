# -*- coding: utf-8 -*-
"""Read-only audit of realtime trifecta odds snapshot timing/coverage.

Goal: determine whether existing v2_realtime_odds_snapshots already supports a
forward-style early-market -> late/actionable-market study. No writes.
"""
from __future__ import annotations
import os
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip()


def one(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


def main():
    if not DB: raise RuntimeError('DATABASE_URL is required')
    print('BAO_RT2_MODE=read_only', flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute("set statement_timeout='120s'")
            r=one(c,"""select count(*) rows, count(distinct race_id) races,
                   min(snapshot_at) first_at, max(snapshot_at) last_at,
                   count(*) filter (where snapshot_at is null) null_snapshot_at
                   from v2_realtime_odds_snapshots""")
            print('BAO_RT2_TOTAL rows:{rows} races:{races} first:{first_at} last:{last_at} null_snapshot_at:{null_snapshot_at}'.format(**r),flush=True)

            c.execute("""select coalesce(snapshot_label,'<NULL>') label, count(*) rows,
                         count(distinct race_id) races, min(snapshot_at) first_at,max(snapshot_at) last_at
                         from v2_realtime_odds_snapshots group by 1 order by races desc,rows desc""")
            for x in c.fetchall():
                print('BAO_RT2_LABEL label:{label} rows:{rows} races:{races} first:{first_at} last:{last_at}'.format(**x),flush=True)

            c.execute("""with s as (
                select o.race_id,o.snapshot_label,min(o.snapshot_at) snapshot_at,count(distinct o.ticket) tickets,
                       max(r.deadline_at) deadline_at
                from v2_realtime_odds_snapshots o join v2_races r on r.race_id=o.race_id
                group by o.race_id,o.snapshot_label)
                select count(*) snapshots,
                       count(*) filter(where tickets=120) full120,
                       count(distinct race_id) races,
                       count(distinct race_id) filter(where tickets=120) races_full120,
                       round(avg(extract(epoch from (deadline_at-snapshot_at))/60.0)::numeric,2) avg_min_before,
                       round(min(extract(epoch from (deadline_at-snapshot_at))/60.0)::numeric,2) min_min_before,
                       round(max(extract(epoch from (deadline_at-snapshot_at))/60.0)::numeric,2) max_min_before
                from s where snapshot_at is not null and deadline_at is not null""")
            x=c.fetchone();print('BAO_RT2_SNAPSHOT_COVERAGE '+' '.join(f'{k}:{v}' for k,v in x.items()),flush=True)

            c.execute("""with s as (
                select o.race_id,o.snapshot_label,min(o.snapshot_at) snapshot_at,count(distinct o.ticket) tickets,
                       max(r.deadline_at) deadline_at
                from v2_realtime_odds_snapshots o join v2_races r on r.race_id=o.race_id
                group by o.race_id,o.snapshot_label), f as (
                select *,extract(epoch from (deadline_at-snapshot_at))/60.0 mb from s
                where tickets=120 and snapshot_at is not null and deadline_at is not null)
                select
                 count(distinct race_id) filter(where mb>=30) ge30,
                 count(distinct race_id) filter(where mb between 15 and 30) m15_30,
                 count(distinct race_id) filter(where mb between 5 and 15) m5_15,
                 count(distinct race_id) filter(where mb between 0 and 5) m0_5,
                 count(distinct race_id) filter(where mb<0) after_deadline
                from f""")
            x=c.fetchone();print('BAO_RT2_TIME_BUCKET_RACES '+' '.join(f'{k}:{v}' for k,v in x.items()),flush=True)

            c.execute("""with s as (
                select o.race_id,o.snapshot_label,min(o.snapshot_at) snapshot_at,count(distinct o.ticket) tickets,
                       max(r.deadline_at) deadline_at
                from v2_realtime_odds_snapshots o join v2_races r on r.race_id=o.race_id
                group by o.race_id,o.snapshot_label), f as (
                select *,extract(epoch from (deadline_at-snapshot_at))/60.0 mb from s
                where tickets=120 and snapshot_at is not null and deadline_at is not null), p as (
                select race_id,
                  bool_or(mb>=20) has_early20,
                  bool_or(mb between 0 and 10) has_late10,
                  bool_or(mb>=15) has_early15,
                  bool_or(mb between 0 and 5) has_late5,
                  count(*) snapshots,
                  max(mb)-min(mb) span_min
                from f group by race_id)
                select count(*) races,
                       count(*) filter(where snapshots>=2) ge2_snapshots,
                       count(*) filter(where has_early20 and has_late10) early20_late10,
                       count(*) filter(where has_early15 and has_late5) early15_late5,
                       count(*) filter(where snapshots>=2 and span_min>=10) span_ge10,
                       round(avg(span_min) filter(where snapshots>=2)::numeric,2) avg_span_ge2
                from p""")
            x=c.fetchone();print('BAO_RT2_PAIR_COVERAGE '+' '.join(f'{k}:{v}' for k,v in x.items()),flush=True)

            c.execute("""with s as (
                select o.race_id,o.snapshot_label,min(o.snapshot_at) snapshot_at,count(distinct o.ticket) tickets,
                       max(r.deadline_at) deadline_at, max(r.race_date) race_date
                from v2_realtime_odds_snapshots o join v2_races r on r.race_id=o.race_id
                group by o.race_id,o.snapshot_label), f as (
                select *,extract(epoch from (deadline_at-snapshot_at))/60.0 mb from s
                where tickets=120 and snapshot_at is not null and deadline_at is not null), p as (
                select race_id,max(race_date) race_date,
                  bool_or(mb>=20) has_early20,bool_or(mb between 0 and 10) has_late10,
                  count(*) snapshots,max(mb)-min(mb) span_min
                from f group by race_id,race_id)
                select race_date,count(*) races,
                       count(*) filter(where snapshots>=2) ge2,
                       count(*) filter(where has_early20 and has_late10) early20_late10
                from p group by race_date order by race_date desc limit 30""")
            for x in c.fetchall():
                print('BAO_RT2_DAY date:{race_date} races:{races} ge2:{ge2} early20_late10:{early20_late10}'.format(**x),flush=True)
    print('BAO_RT2_POLICY=read_only_no_production_change',flush=True)
    print('BAO_RT2_RESULT=PASS_READ_ONLY',flush=True)

if __name__=='__main__': main()
