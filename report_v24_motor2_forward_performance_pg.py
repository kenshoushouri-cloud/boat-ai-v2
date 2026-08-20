# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from db_pg import fetch_all
VERSION='2026-08-20 v24-motor2-forward-performance-v1'
JST=timezone(timedelta(hours=9))
END_DATE=(os.getenv('TARGET_DATE') or datetime.now(JST).strftime('%Y-%m-%d')).strip()
START_DATE=(os.getenv('MOTOR2_FORWARD_REPORT_START_DATE') or '2026-08-20').strip()
UNIT_YEN=max(1,int(os.getenv('MOTOR2_FORWARD_UNIT_YEN',os.getenv('UNIT_YEN','100'))))
REVIEW_TARGETS=[int(x) for x in (os.getenv('MOTOR2_FORWARD_REVIEW_TARGETS') or '10,30,50,100').split(',') if x.strip().isdigit()]
def si(v,d=0):
    try:return int(float(v)) if v not in (None,'') else d
    except:return d
def fetch_rows():return fetch_all('''SELECT * FROM v2_v24_motor2_forward_shadow WHERE race_date >= %s AND race_date <= %s AND evaluated_at IS NOT NULL AND result_ticket IS NOT NULL AND payout_yen>0 ORDER BY race_date,snapshot_at,id''',(START_DATE,END_DATE))
def new():return {'bets':0,'hits':0,'investment':0,'return':0}
def add(s,sel,hit,p):
    if not sel:return
    s['bets']+=1;s['investment']+=UNIT_YEN
    if hit:s['hits']+=1;s['return']+=p
def fmt(n,s):
    b=s['bets'];hr=s['hits']/b*100 if b else 0;roi=s['return']/s['investment']*100 if s['investment'] else 0
    return f"{n}: bets={b} hits={s['hits']} hit_rate={hr:.2f}% investment={s['investment']} return={s['return']} profit={s['return']-s['investment']} ROI={roi:.2f}%"
def latest(rows):
    out={}
    for r in rows:
        k=(str(r.get('race_id') or ''),str(r.get('ticket') or ''),str(r.get('run_class') or ''),str(r.get('window_name') or ''))
        if k not in out or str(r.get('snapshot_at') or '')>=str(out[k].get('snapshot_at') or ''):out[k]=r
    return list(out.values())
def summarize(rows):
    st={'BASE':new(),'MOTOR2':new(),'BOTH':new(),'BASE_ONLY':new(),'MOTOR2_ONLY':new()};tr=defaultdict(int)
    for r in rows:
        p=si(r.get('payout_yen'));hit=str(r.get('ticket') or '')==str(r.get('result_ticket') or '');bs=bool(r.get('base_low_candidate')) or bool(r.get('base_mid_candidate'));ms=bool(r.get('motor2_low_candidate')) or bool(r.get('motor2_mid_candidate'));add(st['BASE'],bs,bs and hit,p);add(st['MOTOR2'],ms,ms and hit,p);t=str(r.get('candidate_transition') or '');tr[t]+=1
        if t in st and t not in ('BASE','MOTOR2'):add(st[t],True,hit,p)
    return st,tr
def scope(label,rows):
    st,tr=summarize(rows);print(f'=== {label} ===');print(f'rows={len(rows)}');print(fmt('BASE',st['BASE']));print(fmt('MOTOR2',st['MOTOR2']));br=st['BASE']['return']/st['BASE']['investment']*100 if st['BASE']['investment'] else 0;mr=st['MOTOR2']['return']/st['MOTOR2']['investment']*100 if st['MOTOR2']['investment'] else 0;print(f'ROI_DELTA MOTOR2-BASE={mr-br:+.2f}pt');print(f"TRANSITIONS BOTH={tr.get('BOTH',0)} BASE_ONLY={tr.get('BASE_ONLY',0)} MOTOR2_ONLY={tr.get('MOTOR2_ONLY',0)} NEITHER={tr.get('NEITHER',0)}")
def prefinal(rows):
    pre={};fin={}
    for r in rows:
        k=(str(r.get('race_id') or ''),str(r.get('ticket') or ''));target=fin if str(r.get('window_name') or '')=='final' else pre
        if k not in target or str(r.get('snapshot_at') or '')>=str(target[k].get('snapshot_at') or ''):target[k]=r
    c=defaultdict(int);matched=0
    for k in set(pre)&set(fin):
        p,f=pre[k],fin[k];pm=bool(p.get('motor2_low_candidate')) or bool(p.get('motor2_mid_candidate'));fm=bool(f.get('motor2_low_candidate')) or bool(f.get('motor2_mid_candidate'));pb=bool(p.get('base_low_candidate')) or bool(p.get('base_mid_candidate'));fb=bool(f.get('base_low_candidate')) or bool(f.get('base_mid_candidate'));c[f'M{int(pm)}{int(fm)}']+=1;c[f'B{int(pb)}{int(fb)}']+=1;matched+=1
    print('=== PRE -> FINAL TRANSITION ===');print(f'matched_race_tickets={matched}');print(f"MOTOR2 kept={c['M11']} dropped={c['M10']} added_final={c['M01']} none={c['M00']}");print(f"BASE kept={c['B11']} dropped={c['B10']} added_final={c['B01']} none={c['B00']}")
def main():
    if not os.getenv('DATABASE_URL'):raise RuntimeError('DATABASE_URL ãå¿è¦ã§ãã')
    print(f'â report_v24_motor2_forward_performance_pg.py VERSION {VERSION}');print(f'PERIOD={START_DATE}..{END_DATE} UNIT_YEN={UNIT_YEN}');print('READ_ONLY=1 PROD_CHANGE=0 LINE=0 BUY=0')
    raw=fetch_rows();rows=latest(raw);print(f'raw_rows={len(raw)} dedup_latest_rows={len(rows)}');scope('OVERALL',rows);pre=[r for r in rows if str(r.get('window_name') or '') in ('morning','day','night')];fin=[r for r in rows if str(r.get('window_name') or '')=='final'];scope('PRE ALL',pre);scope('FINAL',fin)
    for w in ('morning','day','night'):scope(f'PRE {w.upper()}',[r for r in rows if str(r.get('window_name') or '')==w])
    prefinal(rows);mc=sum(1 for r in rows if bool(r.get('motor2_low_candidate')) or bool(r.get('motor2_mid_candidate')));nxt=next((x for x in REVIEW_TARGETS if mc<x),None);print('=== REVIEW PROGRESS ===');print(f'motor2_candidate_rows={mc}');print('next_review_target=completed' if nxt is None else f'next_review_target={nxt} remaining={nxt-mc}');print('RESULT=PASS')
if __name__=='__main__':main()