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


def main():
    if not DB: raise RuntimeError('DATABASE_URL is required')
    print(f'BAO_SMOKE_AUDIT_MODE=read_only target:{TARGET_DATE}', flush=True)
    with psycopg.connect(DB,row_factory=dict_row) as conn:
        with conn.cursor() as c:
            c.execute("""select to_regclass('public.v2_bao_market_shadow_snapshots')::text t""")
            exists=c.fetchone()['t'] is not None
            print(f'BAO_SMOKE_AUDIT_TABLE_EXISTS={int(exists)}', flush=True)
            if not exists:
                print('BAO_SMOKE_AUDIT_RESULT=NO_TABLE', flush=True)
                return
            c.execute("""select phase,count(*) rows,count(distinct race_id) races,
                                min(minutes_before) min_mb,max(minutes_before) max_mb,
                                min(captured_at) first_at,max(captured_at) last_at,
                                min(cardinality(odds)) min_n,max(cardinality(odds)) max_n
                         from v2_bao_market_shadow_snapshots
                         where race_date=%s
                         group by phase order by phase""",(TARGET_DATE,))
            rows=c.fetchall()
            total_rows=0
            for x in rows:
                total_rows += int(x['rows'])
                print('BAO_SMOKE_AUDIT_PHASE=phase:{phase} rows:{rows} races:{races} minutes_before:{min_mb}-{max_mb} odds_n:{min_n}-{max_n} first:{first_at} last:{last_at}'.format(**x), flush=True)
            c.execute("""select count(*) paired from (
                         select race_id from v2_bao_market_shadow_snapshots
                         where race_date=%s group by race_id
                         having count(distinct phase)=2 and count(*)=2) x""",(TARGET_DATE,))
            paired=int(c.fetchone()['paired'])
            c.execute("select pg_total_relation_size('v2_bao_market_shadow_snapshots')::bigint bytes")
            size=int(c.fetchone()['bytes'])
            c.execute("""select count(*) bad from v2_bao_market_shadow_snapshots
                         where race_date=%s and (cardinality(odds)<>120 or phase not in ('early','late'))""",(TARGET_DATE,))
            bad=int(c.fetchone()['bad'])
            print(f'BAO_SMOKE_AUDIT_SUMMARY=rows:{total_rows} paired:{paired} bad:{bad} table_bytes:{size}', flush=True)
            if bad:
                raise SystemExit('invalid compact rows found')
            print('BAO_SMOKE_AUDIT_RESULT=' + ('ROWS_PRESENT' if total_rows else 'ZERO_ROWS'), flush=True)

if __name__=='__main__': main()
