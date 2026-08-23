# -*- coding: utf-8 -*-
"""Read-only live probe for BOAT RACE official trifecta odds parsing.
No DB writes and no response persistence.
"""
from __future__ import annotations
import os,re
from datetime import datetime,timedelta,timezone
import psycopg
from psycopg.rows import dict_row
import v21_realtime_collector_pg as rt

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
    for r in rows:
        url=rt._official_url('odds3t',str(r['race_date']),str(r['venue_id']).zfill(2),int(r['race_no']))
        html=rt._fetch(url)
        parsed=rt.parse_odds3t(html or '') if html else {}
        text=rt._soup_text(html or '') if html else ''
        # Structural diagnostics only; never print raw HTML or URLs.
        hyphen_tickets=len(re.findall(r'[1-6]\s*[-－]\s*[1-6]\s*[-－]\s*[1-6]',text))
        decimal_tokens=len(re.findall(r'(?<!\d)\d{1,4}\.\d(?!\d)',text))
        table_rows=len(rt._extract_table_rows(html or '')) if html else 0
        no_data=int(rt._looks_no_data(html or ''))
        print(f"BAO_ODDS_PROBE_CASE=race:{r['race_id']} venue:{r['venue_id']} rno:{r['race_no']} mb:{float(r['mb']):.2f} html:{len(html or '')} text:{len(text)} tables:{table_rows} hyphen_tickets:{hyphen_tickets} decimal_tokens:{decimal_tokens} parsed:{len(parsed)} no_data:{no_data}",flush=True)
        if html and table_rows:
            # Report only cell-count shapes, not page contents.
            shapes={}
            for cells in rt._extract_table_rows(html):
                shapes[len(cells)]=shapes.get(len(cells),0)+1
            shape_txt=','.join(f'{k}:{v}' for k,v in sorted(shapes.items()))
            print(f"BAO_ODDS_PROBE_SHAPES=race:{r['race_id']} cells_per_row:{shape_txt}",flush=True)
    print('BAO_ODDS_PROBE_RESULT=PASS_READ_ONLY',flush=True)

if __name__=='__main__': main()
