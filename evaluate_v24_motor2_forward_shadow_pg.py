# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from collections import defaultdict
from typing import Any, Dict, List, Tuple
from db_pg import execute, fetch_all
VERSION='2026-08-20 v24-motor2-forward-evaluator-v2-daily-all-snapshots'
TARGET_DATE=(os.getenv('TARGET_DATE') or '').strip(); SNAPSHOT_KEY=(os.getenv('SNAPSHOT_KEY') or '').strip(); RUN_CLASS=(os.getenv('RUN_CLASS') or '').strip(); WINDOW_NAME=(os.getenv('WINDOW_NAME') or '').strip(); UNIT_YEN=max(1,int(os.getenv('MOTOR2_EVAL_UNIT_YEN',os.getenv('UNIT_YEN','100'))))
def _safe_int(v:Any,d:int=0)->int:
    try:return int(float(v)) if v not in (None,'') else d
    except Exception:return d
def _norm_ticket(v:Any)->str:return str(v or '').strip()
def _where_sql(alias='s')->Tuple[str,List[Any]]:
    c=[];p=[]
    for val,col in [(TARGET_DATE,'race_date'),(SNAPSHOT_KEY,'snapshot_key'),(RUN_CLASS,'run_class'),(WINDOW_NAME,'window_name')]:
        if val:c.append(f'{alias}.{col} = %s');p.append(val)
    return ((' AND '+' AND '.join(c)) if c else '',p)
def _fetch_targets():
    extra,params=_where_sql('s')
    return fetch_all(f'''SELECT s.*,r.result_status,r.race_status,r.trifecta_ticket AS official_ticket,r.trifecta_payout_yen AS official_payout FROM v2_v24_motor2_forward_shadow s LEFT JOIN v2_results r ON r.race_id=s.race_id WHERE 1=1 {extra} ORDER BY s.race_date,s.snapshot_at,s.race_id,s.ticket,s.id''',tuple(params))
def _evaluable(r):return str(r.get('result_status') or '').lower()=='official' and str(r.get('race_status') or '').lower()=='official' and bool(_norm_ticket(r.get('official_ticket'))) and _safe_int(r.get('official_payout'),0)>0
def _update(r):
    ot=_norm_ticket(r.get('official_ticket'));po=_safe_int(r.get('official_payout'),0);hit=_norm_ticket(r.get('ticket'))==ot;bs=bool(r.get('base_low_candidate')) or bool(r.get('base_mid_candidate'));ms=bool(r.get('motor2_low_candidate')) or bool(r.get('motor2_mid_candidate'))
    execute('''UPDATE v2_v24_motor2_forward_shadow SET result_ticket=%s,payout_yen=%s,base_hit=%s,motor2_hit=%s,evaluated_at=now(),updated_at=now() WHERE id=%s''',(ot,po,bool(bs and hit),bool(ms and hit),r['id']))
def _new():return {'bets':0,'hits':0,'investment':0,'return':0}
def _add(s,sel,hit,payout):
    if not sel:return
    s['bets']+=1;s['investment']+=UNIT_YEN
    if hit:s['hits']+=1;s['return']+=payout
def _fmt(name,s):
    b=s['bets'];hr=s['hits']/b*100 if b else 0;roi=s['return']/s['investment']*100 if s['investment'] else 0
    return f"{name}: bets={b} hits={s['hits']} hit_rate={hr:.2f}% investment={s['investment']} return={s['return']} profit={s['return']-s['investment']} ROI={roi:.2f}%"
def _scope(label,rows):
    st={'BASE':_new(),'MOTOR2':_new()};tr=defaultdict(int);ev=pend=0
    for r in rows:
        rt=_norm_ticket(r.get('result_ticket'));po=_safe_int(r.get('payout_yen'),0)
        if not (r.get('evaluated_at') and rt and po>0):pend+=1;continue
        ev+=1;hit=_norm_ticket(r.get('ticket'))==rt;bs=bool(r.get('base_low_candidate')) or bool(r.get('base_mid_candidate'));ms=bool(r.get('motor2_low_candidate')) or bool(r.get('motor2_mid_candidate'));_add(st['BASE'],bs,bs and hit,po);_add(st['MOTOR2'],ms,ms and hit,po);tr[str(r.get('candidate_transition') or '')]+=1
    print(f'=== {label} ===');print(f'rows={len(rows)} evaluated={ev} pending={pend}');print(_fmt('BASE',st['BASE']));print(_fmt('MOTOR2',st['MOTOR2']));br=st['BASE']['return']/st['BASE']['investment']*100 if st['BASE']['investment'] else 0;mr=st['MOTOR2']['return']/st['MOTOR2']['investment']*100 if st['MOTOR2']['investment'] else 0;print(f'ROI_DELTA MOTOR2-BASE={mr-br:+.2f}pt');print(f"TRANSITIONS BOTH={tr.get('BOTH',0)} BASE_ONLY={tr.get('BASE_ONLY',0)} MOTOR2_ONLY={tr.get('MOTOR2_ONLY',0)} NEITHER={tr.get('NEITHER',0)}")
def main():
    if not os.getenv('DATABASE_URL'):raise RuntimeError('DATABASE_URL ãå¿è¦ã§ãã')
    print(f'â evaluate_v24_motor2_forward_shadow_pg.py VERSION {VERSION}');print(f"TARGET_DATE={TARGET_DATE or 'ALL'} SNAPSHOT_KEY={SNAPSHOT_KEY or 'ALL'} RUN_CLASS={RUN_CLASS or 'ALL'} WINDOW_NAME={WINDOW_NAME or 'ALL'} UNIT_YEN={UNIT_YEN}");print('LINE=0 BUY=0 PROD_V24_CHANGE=0 N02_CHANGE=0')
    rows=_fetch_targets();updated=not_ready=already=0
    for r in rows:
        if not _evaluable(r):not_ready+=1;continue
        if r.get('evaluated_at') is not None and _norm_ticket(r.get('result_ticket'))==_norm_ticket(r.get('official_ticket')) and _safe_int(r.get('payout_yen'),0)==_safe_int(r.get('official_payout'),0):already+=1;continue
        _update(r);updated+=1
    print('=== UPDATE SUMMARY ===');print(f'rows_loaded={len(rows)} updated_rows={updated} already_evaluated={already} result_not_ready={not_ready}')
    rows=_fetch_targets();_scope('OVERALL',rows);g=defaultdict(list)
    for r in rows:g[(str(r.get('run_class') or ''),str(r.get('window_name') or ''))].append(r)
    print('=== BY RUN_CLASS / WINDOW ===')
    for k in sorted(g):_scope(f'{k[0]} / {k[1]}',g[k])
    print('RESULT=PASS')
if __name__=='__main__':main()