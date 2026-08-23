# -*- coding: utf-8 -*-
"""Read-only post-audit for the isolated Bao early/late market Shadow smoke."""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
import psycopg
from psycopg.rows import dict_row

JST=timezone(timedelta(hours=9))
DB=os.getenv('DATABASE_URL','').strip()
TARGET_DATE=os.getenv('TARGET_DATE') or datetime.now(JST).strftime('%Y-%m-%d')
AUDIT_AT=datetime.fromisoformat(os.getenv('BAO_SMOKE_AUDIT_AT','2026-08-23T09:19:10+09:00'))


def main():
    if not DB: raise RuntimeError('DATABASE_URL is required')
    print(f'BAO_SMOKE_AUDIT_MODE=read_only target:{TARGET_DATE} audit_at:{AUDIT_AT.isoformat()}', flush=True)
    with psycopg.connect(DB,row_factory=dict_row) as conn:
        with conn.cursor() as c:
            c.execute("""select race_id,race_no,coalesce(venue_id,venue_code) venue_id,deadline_at,
                                extract(epoch from (deadline_at-%s::timestamptz))/60.0 minutes_before
                         from v2_races
                         where race_date=%s and deadline_at is not null
                           and ((extract(epoch from (deadline_at-%s::timestamptz))/60.0 between 20 and 30)
                             or (extract(epoch from (deadline_at-%s::timestamptz))/60.0 between 0 and 7))
                         order by deadline_at""",(AUDIT_AT,TARGET_DATE,AUDIT_AT,AUDIT_AT))
            eligible=c.fetchall()
            print(f'BAO_SMOKE_AUDIT_ELIGIBLE_AT_RUN={len(eligible)}', flush=True)
            for x in eligible:
                mb=float(x['minutes_before']); phase='early' if 20 <= mb <= 30 else 'late'
                print(f"BAO_SMOKE_AUDIT_TARGET=race:{x['race_id']} venue:{x['venue_id']} rno:{x['race_no']} phase:{phase} minutes_before:{mb:.2f} deadline:{x['deadline_at']}", flush=True)
            c.execute("select to_regclass('public.v2_bao_market_shadow_snapshots')::text t")
            exists=c.fetchone()['t'] is not None
            print(f'BAO_SMOKE_AUDIT_TABLE_EXISTS={int(exists)}', flush=True)
            if not exists:
                print('BAO_SMOKE_AUDIT_RESULT=NO_TABLE', flush=True); return
            c.execute("""select race_id,phase,minutes_before,cardinality(odds) odds_n,captured_at
                         from v2_bao_market_shadow_snapshots where race_date=%s order by captured_at""",(TARGET_DATE,))
            shadow=c.fetchall()
            for r in shadow:
                print(f"BAO_SMOKE_AUDIT_ROW=race:{r['race_id']} phase:{r['phase']} minutes_before:{float(r['minutes_before']):.2f} odds_n:{r['odds_n']} captured_at:{r['captured_at']}", flush=True)
            c.execute("""select count(*) paired from (select race_id from v2_bao_market_shadow_snapshots
                         where race_date=%s group by race_id having count(distinct phase)=2 and count(*)=2) x""",(TARGET_DATE,))
            paired=int(c.fetchone()['paired'])
            c.execute("""select count(*) bad from v2_bao_market_shadow_snapshots
                         where race_date=%s and (cardinality(odds)<>120 or phase not in ('early','late'))""",(TARGET_DATE,))
            bad=int(c.fetchone()['bad'])
            print(f'BAO_SMOKE_AUDIT_SUMMARY=rows:{len(shadow)} paired:{paired} bad:{bad}', flush=True)
            if bad: raise SystemExit('invalid compact rows found')
            print('BAO_SMOKE_AUDIT_RESULT=' + ('ROWS_PRESENT' if shadow else ('ELIGIBLE_BUT_ZERO_ROWS' if eligible else 'NO_ELIGIBLE_TARGETS_AT_RUN')), flush=True)

if __name__=='__main__': main()
