# -*- coding: utf-8 -*-
from __future__ import annotations
import os, subprocess, sys, time
from calendar import monthrange
from datetime import datetime
from pathlib import Path
from db_pg import fetch_all, fetch_one

TARGET_MONTH = os.getenv('HISTORICAL_GAP_REPAIR_MONTH', '2025-12').strip()
WORKERS = int(os.getenv('HISTORICAL_GAP_REPAIR_WORKERS', '4'))
ODDS_WORKERS = int(os.getenv('HISTORICAL_GAP_REPAIR_ODDS_WORKERS', '4'))
SLEEP_SEC = float(os.getenv('HISTORICAL_GAP_REPAIR_SLEEP_SEC', '0.1'))

def month_bounds(ym):
    dt = datetime.strptime(ym, '%Y-%m')
    last = monthrange(dt.year, dt.month)[1]
    start = f'{dt.year:04d}-{dt.month:02d}-01'
    end = f'{dt.year:04d}-{dt.month:02d}-{last:02d}'
    nxt = f'{dt.year+1:04d}-01-01' if dt.month == 12 else f'{dt.year:04d}-{dt.month+1:02d}-01'
    return start, end, nxt

def targets(start, nxt):
    sr, nr = start.replace('-', ''), nxt.replace('-', '')
    return fetch_all('''
        with oc as (
            select race_id, count(distinct ticket) ticket_count
            from v2_odds_trifecta
            where race_id >= %s and race_id < %s
            group by race_id
        )
        select r.race_id, r.race_date, r.venue_id, r.race_no,
               coalesce(oc.ticket_count,0) ticket_count,
               rs.trifecta_ticket, rs.trifecta_payout_yen
        from v2_races r
        join v2_results rs on rs.race_id=r.race_id
        left join oc on oc.race_id=r.race_id
        where r.race_date >= %s and r.race_date < %s
          and rs.trifecta_ticket is not null
          and rs.trifecta_payout_yen > 0
          and coalesce(oc.ticket_count,0) not in (120,60,24)
        order by r.race_date,r.venue_id,r.race_no
    ''', (sr, nr, start, nxt))

def audit(start, nxt):
    sr, nr = start.replace('-', ''), nxt.replace('-', '')
    b = fetch_one('''
        select count(*) races,
               count(*) filter(where rs.trifecta_ticket is not null and rs.trifecta_payout_yen>0) valid_results
        from v2_races r left join v2_results rs on rs.race_id=r.race_id
        where r.race_date >= %s and r.race_date < %s
    ''', (start, nxt)) or {}
    ods = fetch_all('''
        select race_id,count(distinct ticket) ticket_count
        from v2_odds_trifecta where race_id >= %s and race_id < %s group by race_id
    ''', (sr, nr))
    return {
        'races': int(b.get('races') or 0),
        'valid_results': int(b.get('valid_results') or 0),
        'odds_races': len(ods),
        'complete_expected': sum(1 for x in ods if int(x.get('ticket_count') or 0) in (120,60,24)),
        'partial': sum(1 for x in ods if int(x.get('ticket_count') or 0) not in (120,60,24)),
    }

def main():
    if not os.getenv('DATABASE_URL'):
        raise RuntimeError('DATABASE_URL ãå¿è¦ã§ãã')
    start, end, nxt = month_bounds(TARGET_MONTH)
    print('â run_historical_month_gap_repair_pg.py VERSION 2026-08-10 targeted-gap-repair-v2', flush=True)
    print(f'TARGET_MONTH={TARGET_MONTH} PERIOD={start}..{end}', flush=True)
    before = audit(start, nxt)
    print('BEFORE ' + ' '.join(f'{k}={v}' for k,v in before.items()), flush=True)
    rows = targets(start, nxt)
    print(f'gap_targets={len(rows)}', flush=True)
    for r in rows[:30]:
        print(f"  {r['race_id']} tickets={int(r.get('ticket_count') or 0)} result={r.get('trifecta_ticket')} payout={r.get('trifecta_payout_yen')}", flush=True)
    if not rows:
        print('åè£ä¿®å¯¾è±¡ã¯ããã¾ããã', flush=True); return
    base = Path(__file__).resolve().parent
    repair = base / 'repair_month_all_pg.py'
    if not repair.exists():
        raise FileNotFoundError(f'repair_month_all_pg.py ãè¦ã¤ããã¾ãã: {repair}')
    env = os.environ.copy()
    env.update({
        'REPAIR_START_DATE': start, 'REPAIR_END_DATE': end,
        'REPAIR_RACE_IDS': ','.join(str(r['race_id']) for r in rows),
        'REPAIR_DO_RACES': '0', 'REPAIR_DO_RESULTS': '0', 'REPAIR_DO_ODDS': '1',
        'ODDS_IS_FINAL': '1', 'REPAIR_WORKERS': str(WORKERS),
        'REPAIR_ODDS_WORKERS': str(ODDS_WORKERS), 'REPAIR_SLEEP_SEC': str(SLEEP_SEC),
        'PYTHONUNBUFFERED': '1'
    })
    print(f'TARGETED GAP REPAIR START targets={len(rows)}', flush=True)
    t0=time.monotonic()
    p=subprocess.run([sys.executable,'-u',str(repair)],cwd=str(base),env=env,text=True,check=False)
    print(f'TARGETED GAP REPAIR END returncode={p.returncode} elapsed={time.monotonic()-t0:.1f}s', flush=True)
    if p.returncode != 0:
        raise RuntimeError(f'repair_month_all_pg.py failed returncode={p.returncode}')
    after=audit(start,nxt); remain=targets(start,nxt)
    print('=== targeted gap repair audit ===', flush=True)
    print('AFTER ' + ' '.join(f'{k}={v}' for k,v in after.items()), flush=True)
    print(f'gap_targets_before={len(rows)} gap_targets_remaining={len(remain)} improved={len(rows)-len(remain)}', flush=True)
    print('TARGETED_GAP_REPAIR=PASS' if not remain else 'TARGETED_GAP_REPAIR=PARTIAL', flush=True)

if __name__ == '__main__':
    main()