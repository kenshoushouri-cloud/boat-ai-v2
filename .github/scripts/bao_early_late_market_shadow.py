# -*- coding: utf-8 -*-
"""Isolated compact early/late trifecta market Shadow collector.

Writes ONLY v2_bao_market_shadow_snapshots. One row stores one complete
race/phase snapshot as a fixed canonical-order real[120] odds vector.
Production prediction/decision/LINE tables are never touched.
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
import psycopg
from psycopg.rows import dict_row
import v21_realtime_collector_pg as rt

JST=timezone(timedelta(hours=9))
DB=os.getenv('DATABASE_URL','').strip()
TARGET_DATE=os.getenv('TARGET_DATE') or datetime.now(JST).strftime('%Y-%m-%d')
EARLY_MIN_LO=float(os.getenv('BAO_EARLY_MIN_LO','20'))
EARLY_MIN_HI=float(os.getenv('BAO_EARLY_MIN_HI','30'))
LATE_MIN_LO=float(os.getenv('BAO_LATE_MIN_LO','0'))
LATE_MIN_HI=float(os.getenv('BAO_LATE_MIN_HI','7'))
CANONICAL_TICKETS=tuple(f'{a}-{b}-{c}' for a in range(1,7) for b in range(1,7) if b!=a for c in range(1,7) if c not in (a,b))
assert len(CANONICAL_TICKETS)==120 and len(set(CANONICAL_TICKETS))==120

DDL="""
create table if not exists v2_bao_market_shadow_snapshots (
 race_id text not null,
 race_date date not null,
 venue_id text not null,
 race_no smallint not null,
 phase text not null check (phase in ('early','late')),
 captured_at timestamptz not null,
 deadline_at timestamptz not null,
 minutes_before real not null,
 odds real[] not null,
 source text not null default 'official_odds3t',
 schema_version smallint not null default 2,
 created_at timestamptz not null default now(),
 primary key (race_id,phase),
 check (cardinality(odds)=120)
)
"""


def phase_for(minutes_before: float):
    if EARLY_MIN_LO <= minutes_before <= EARLY_MIN_HI: return 'early'
    if LATE_MIN_LO <= minutes_before <= LATE_MIN_HI: return 'late'
    return None


def _assert_compact_schema(conn):
    with conn.cursor() as c:
        c.execute("""select data_type,udt_name from information_schema.columns
                     where table_schema='public' and table_name='v2_bao_market_shadow_snapshots' and column_name='odds'""")
        row=c.fetchone()
        if not row or row['data_type']!='ARRAY' or row['udt_name']!='_float4':
            raise RuntimeError('Bao market Shadow table exists with unexpected/noncompact schema')


def main():
    if not DB: raise RuntimeError('DATABASE_URL is required')
    now=datetime.now(JST)
    print(f'BAO_SHADOW_MODE=isolated_compact_write target:{TARGET_DATE} now:{now.isoformat()}',flush=True)
    print(f'BAO_SHADOW_WINDOWS=early:{EARLY_MIN_LO}-{EARLY_MIN_HI} late:{LATE_MIN_LO}-{LATE_MIN_HI}',flush=True)
    print('BAO_SHADOW_SCHEMA=v2_one_row_per_race_phase_real120',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute(DDL)
            c.execute("create index if not exists ix_v2_bao_market_shadow_phase_time on v2_bao_market_shadow_snapshots(phase,captured_at)")
        _assert_compact_schema(conn)
        with conn.cursor() as c:
            c.execute("""select race_id,race_date,coalesce(venue_id,venue_code) venue_id,race_no,deadline_at
                         from v2_races where race_date=%s and deadline_at is not null order by deadline_at""",(TARGET_DATE,))
            races=[dict(x) for x in c.fetchall()]
        targets=[]
        for r in races:
            dl=r['deadline_at']
            if dl.tzinfo is None: dl=dl.replace(tzinfo=JST)
            dl=dl.astimezone(JST)
            mb=(dl-now).total_seconds()/60.0
            ph=phase_for(mb)
            if ph: targets.append((r,ph,mb,dl))
        print(f'BAO_SHADOW_TARGETS={len(targets)}',flush=True)
        saved_races=0;saved_rows=0;partial=0;skipped_existing=0
        for r,ph,mb,dl in targets:
            rid=str(r['race_id']);venue=str(r['venue_id']).zfill(2);rno=int(r['race_no'])
            with conn.cursor() as c:
                c.execute("select 1 ok from v2_bao_market_shadow_snapshots where race_id=%s and phase=%s",(rid,ph))
                if c.fetchone(): skipped_existing+=1;continue
            html=rt._fetch(rt._official_url('odds3t',TARGET_DATE,venue,rno))
            odds=rt.parse_odds3t(html or '') if html else {}
            if len(odds)!=120 or set(odds)!=set(CANONICAL_TICKETS):
                partial+=1
                print(f'BAO_SHADOW_SKIP race:{rid} phase:{ph} odds:{len(odds)} reason:not_exact120',flush=True)
                continue
            captured=datetime.now(JST)
            mb2=(dl-captured).total_seconds()/60.0
            odds_vec=[float(odds[t]) for t in CANONICAL_TICKETS]
            with conn.cursor() as c:
                c.execute("""insert into v2_bao_market_shadow_snapshots
                    (race_id,race_date,venue_id,race_no,phase,captured_at,deadline_at,minutes_before,odds)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    on conflict (race_id,phase) do nothing""",
                    (rid,r['race_date'],venue,rno,ph,captured,dl,round(mb2,3),odds_vec))
                wrote=c.rowcount
            if wrote:
                saved_races+=1;saved_rows+=1
                print(f'BAO_SHADOW_SAVE race:{rid} phase:{ph} rows:1 odds_n:120 minutes_before:{mb2:.2f}',flush=True)
            else:
                skipped_existing+=1
        with conn.cursor() as c:
            c.execute("""select phase,count(*) rows,count(distinct race_id) races,min(captured_at) first_at,max(captured_at) last_at,
                                min(cardinality(odds)) min_n,max(cardinality(odds)) max_n
                         from v2_bao_market_shadow_snapshots group by phase order by phase""")
            for x in c.fetchall():
                print('BAO_SHADOW_TOTAL phase:{phase} rows:{rows} races:{races} odds_n:{min_n}-{max_n} first:{first_at} last:{last_at}'.format(**x),flush=True)
            c.execute("""select count(*) paired_races from (
                         select race_id from v2_bao_market_shadow_snapshots
                         group by race_id having count(distinct phase)=2 and count(*)=2) x""")
            print(f"BAO_SHADOW_PAIRED_RACES={c.fetchone()['paired_races']}",flush=True)
            c.execute("select pg_total_relation_size('v2_bao_market_shadow_snapshots')::bigint bytes")
            print(f"BAO_SHADOW_TABLE_BYTES={c.fetchone()['bytes']}",flush=True)
    print(f'BAO_SHADOW_RUN saved_races:{saved_races} saved_rows:{saved_rows} partial:{partial} skipped_existing:{skipped_existing}',flush=True)
    print('BAO_SHADOW_POLICY=isolated_compact_table_only_no_production_decision_change',flush=True)
    print('BAO_SHADOW_RESULT=PASS',flush=True)

if __name__=='__main__': main()
