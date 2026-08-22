# -*- coding: utf-8 -*-
"""Isolated early/late trifecta market shadow collector.

Writes ONLY v2_bao_market_shadow_snapshots. It never changes Production
prediction/decision/LINE tables. First successful snapshot for each
(race_id, phase, ticket) is frozen with ON CONFLICT DO NOTHING.
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

DDL="""
create table if not exists v2_bao_market_shadow_snapshots (
 id bigserial primary key,
 race_id text not null,
 race_date date not null,
 venue_id text not null,
 race_no integer not null,
 phase text not null check (phase in ('early','late')),
 captured_at timestamptz not null,
 deadline_at timestamptz not null,
 minutes_before numeric not null,
 ticket text not null,
 odds numeric not null,
 source text not null default 'official_odds3t',
 created_at timestamptz not null default now(),
 unique (race_id,phase,ticket)
)
"""


def phase_for(minutes_before: float):
    if EARLY_MIN_LO <= minutes_before <= EARLY_MIN_HI: return 'early'
    if LATE_MIN_LO <= minutes_before <= LATE_MIN_HI: return 'late'
    return None


def main():
    if not DB: raise RuntimeError('DATABASE_URL is required')
    now=datetime.now(JST)
    print(f'BAO_SHADOW_MODE=isolated_write target:{TARGET_DATE} now:{now.isoformat()}',flush=True)
    print(f'BAO_SHADOW_WINDOWS=early:{EARLY_MIN_LO}-{EARLY_MIN_HI} late:{LATE_MIN_LO}-{LATE_MIN_HI}',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute(DDL)
            c.execute("create index if not exists ix_v2_bao_market_shadow_phase_time on v2_bao_market_shadow_snapshots(phase,captured_at)")
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
                c.execute("select count(*) n from v2_bao_market_shadow_snapshots where race_id=%s and phase=%s",(rid,ph))
                if int(c.fetchone()['n'])>=120:
                    skipped_existing+=1;continue
            html=rt._fetch(rt._official_url('odds3t',TARGET_DATE,venue,rno))
            odds=rt.parse_odds3t(html or '') if html else {}
            if len(odds)!=120:
                partial+=1
                print(f'BAO_SHADOW_SKIP race:{rid} phase:{ph} odds:{len(odds)} reason:not120',flush=True)
                continue
            captured=datetime.now(JST)
            rows=[(rid,r['race_date'],venue,rno,ph,captured,dl,round((dl-captured).total_seconds()/60.0,3),ticket,float(odd)) for ticket,odd in odds.items()]
            with conn.cursor() as c:
                c.executemany("""insert into v2_bao_market_shadow_snapshots
                    (race_id,race_date,venue_id,race_no,phase,captured_at,deadline_at,minutes_before,ticket,odds)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    on conflict (race_id,phase,ticket) do nothing""",rows)
            saved_races+=1;saved_rows+=len(rows)
            print(f'BAO_SHADOW_SAVE race:{rid} phase:{ph} rows:120 minutes_before:{mb:.2f}',flush=True)
        with conn.cursor() as c:
            c.execute("""select phase,count(*) rows,count(distinct race_id) races,min(captured_at) first_at,max(captured_at) last_at
                         from v2_bao_market_shadow_snapshots group by phase order by phase""")
            for x in c.fetchall():
                print('BAO_SHADOW_TOTAL phase:{phase} rows:{rows} races:{races} first:{first_at} last:{last_at}'.format(**x),flush=True)
            c.execute("""select count(*) paired_races from (
                         select race_id from v2_bao_market_shadow_snapshots
                         group by race_id having count(distinct phase)=2 and count(*)=240) x""")
            print(f"BAO_SHADOW_PAIRED_RACES={c.fetchone()['paired_races']}",flush=True)
    print(f'BAO_SHADOW_RUN saved_races:{saved_races} saved_rows:{saved_rows} partial:{partial} skipped_existing:{skipped_existing}',flush=True)
    print('BAO_SHADOW_POLICY=isolated_table_only_no_production_decision_change',flush=True)
    print('BAO_SHADOW_RESULT=PASS',flush=True)

if __name__=='__main__': main()
