# -*- coding: utf-8 -*-
"""Read-only live probe for BOAT RACE official trifecta odds parsing."""
from __future__ import annotations
import os,re
from datetime import datetime,timedelta,timezone
import psycopg
from psycopg.rows import dict_row
import v21_realtime_collector_pg as rt
import bao_early_late_market_shadow as bao

JST=timezone(timedelta(hours=9))
DB=os.getenv('DATABASE_URL','').strip()

def main():
    if not DB: raise RuntimeError('DATABASE_URL is required')
    now=datetime.now(JST)
    print(f'BAO_ODDS_PROBE_MODE=read_only now:{now.isoformat()}',flush=True)
    with psycopg.connect(DB,row_factory=dict_row) as conn, conn.cursor() as c:
        c.execute("""select race_id,race_date,coalesce(venue_id,venue_code) venue_id,race_no,deadline_at,
                            extract(epoch from (deadline_at-%s))/60.0 mb
                     from v2_races
                     where race_date=%s and deadline_at>%s and deadline_at<=%s + interval '60 minutes'
                     order by deadline_at limit 6""",(now,now.date(),now,now))
        rows=c.fetchall()
    print(f'BAO_ODDS_PROBE_TARGETS={len(rows)}',flush=True)
    complete=0
    for r in rows:
        html=rt._fetch(rt._official_url('odds3t',str(r['race_date']),str(r['venue_id']).zfill(2),int(r['race_no'])))
        legacy=rt.parse_odds3t(html or '') if html else {}
        parsed=bao.parse_official_odds3t(html or '') if html else {}
        text=rt._soup_text(html or '') if html else ''
        table_rows=len(rt._extract_table_rows(html or '')) if html else 0
        no_data=int(rt._looks_no_data(html or ''))
        decimal_tokens=len(re.findall(r'(?<!\d)\d{1,4}\.\d(?!\d)',text))
        valid_set=int(set(parsed)==bao.CANONICAL_SET) if len(parsed)==120 else 0
        complete+=int(len(parsed)==120 and valid_set)
        print(f"BAO_ODDS_PROBE_CASE=race:{r['race_id']} venue:{r['venue_id']} rno:{r['race_no']} mb:{float(r['mb']):.2f} html:{len(html or '')} tables:{table_rows} decimals:{decimal_tokens} legacy:{len(legacy)} table_parser:{len(parsed)} valid_set:{valid_set} no_data:{no_data}",flush=True)
    print(f'BAO_ODDS_PROBE_COMPLETE={complete}/{len(rows)}',flush=True)
    if rows and complete==0:
        raise SystemExit('Bao table parser produced no complete live cases')
    print('BAO_ODDS_PROBE_RESULT=PASS_READ_ONLY',flush=True)

if __name__=='__main__': main()
