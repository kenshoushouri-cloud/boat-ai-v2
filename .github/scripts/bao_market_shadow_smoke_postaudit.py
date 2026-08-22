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
# Second owner-only smoke was posted just after the 08:56:20 JST clock check.
AUDIT_AT=datetime.fromisoformat(os.getenv('BAO_SMOKE_AUDIT_AT','2026-08-23T08:56:25+09:00'))


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
            for x in eligible[:20]:
                mb=float(x['minutes_before']); phase='early' if 20 <= mb <= 30 else 'late'
                print(f"BAO_SMOKE_AUDIT_TARGET=race:{x['race_id']} venue:{x['venue_id']} rno:{x['race_no']} phase:{phase} minutes_before:{mb:.2f} deadline:{x['deadline_at']}", flush=True)
            for x in eligible:
                rid=str(x['race_id'])
                c.execute("""select snapshot_label,min(snapshot_at) first_at,max(snapshot_at) last_at,
                                    count(*) rows,count(distinct ticket) tickets
                             from v2_realtime_odds_snapshots
                             where race_id=%s and snapshot_at between %s::timestamptz - interval '30 minutes'
                                                        and %s::timestamptz + interval '30 minutes'
                             group by snapshot_label order by first_at""",(rid,AUDIT_AT,AUDIT_AT))
                rt_rows=c.fetchall()
                print(f'BAO_SMOKE_RT_GROUPS=race:{rid} groups:{len(rt_rows)}', flush=True)
                for r in rt_rows:
                    print(f"BAO_SMOKE_RT_GROUP=race:{rid} label:{r['snapshot_label']} rows:{r['rows']} tickets:{r['tickets']} first:{r['first_at']} last:{r['last_at']}", flush=True)
                c.execute("""select count(*) rows,count(distinct ticket) tickets,min(snapshot_at) first_at,max(snapshot_at) last_at
                             from v2_realtime_odds_snapshots where race_id=%s and snapshot_at <= %s::timestamptz""",(rid,AUDIT_AT))
                before=c.fetchone()
                print(f"BAO_SMOKE_RT_BEFORE=race:{rid} rows:{before['rows']} tickets:{before['tickets']} first:{before['first_at']} last:{before['last_at']}", flush=True)

            c.execute("select to_regclass('public.v2_bao_market_shadow_snapshots')::text t")
            exists=c.fetchone()['t'] is not None
            print(f'BAO_SMOKE_AUDIT_TABLE_EXISTS={int(exists)}', flush=True)
            if not exists:
                print('BAO_SMOKE_AUDIT_RESULT=NO_TABLE', flush=True); return
            c.execute("""select phase,count(*) rows,count(distinct race_id) races,
                                min(minutes_before) min_mb,max(minutes_before) max_mb,
                                min(captured_at) first_at,max(captured_at) last_at,
                                min(cardinality(odds)) min_n,max(cardinality(odds)) max_n
                         from v2_bao_market_shadow_snapshots where race_date=%s
                         group by phase order by phase""",(TARGET_DATE,))
            rows=c.fetchall(); total_rows=0
            for x in rows:
                total_rows += int(x['rows'])
                print('BAO_SMOKE_AUDIT_PHASE=phase:{phase} rows:{rows} races:{races} minutes_before:{min_mb}-{max_mb} odds_n:{min_n}-{max_n} first:{first_at} last:{last_at}'.format(**x), flush=True)
            c.execute("""select count(*) paired from (select race_id from v2_bao_market_shadow_snapshots
                         where race_date=%s group by race_id having count(distinct phase)=2 and count(*)=2) x""",(TARGET_DATE,))
            paired=int(c.fetchone()['paired'])
            c.execute("select pg_total_relation_size('v2_bao_market_shadow_snapshots')::bigint bytes")
            size=int(c.fetchone()['bytes'])
            c.execute("""select count(*) bad from v2_bao_market_shadow_snapshots
                         where race_date=%s and (cardinality(odds)<>120 or phase not in ('early','late'))""",(TARGET_DATE,))
            bad=int(c.fetchone()['bad'])
            print(f'BAO_SMOKE_AUDIT_SUMMARY=rows:{total_rows} eligible_at_run:{len(eligible)} paired:{paired} bad:{bad} table_bytes:{size}', flush=True)
            if bad: raise SystemExit('invalid compact rows found')
            if total_rows: result='ROWS_PRESENT'
            elif eligible: result='ELIGIBLE_BUT_ZERO_ROWS'
            else: result='NO_ELIGIBLE_TARGETS_AT_RUN'
            print(f'BAO_SMOKE_AUDIT_RESULT={result}', flush=True)

if __name__=='__main__': main()
