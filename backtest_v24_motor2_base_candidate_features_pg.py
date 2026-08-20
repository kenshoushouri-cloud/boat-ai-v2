# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from collections import defaultdict
from typing import Any, Dict, List
from db_pg import fetch_all
import backtest_v24_motor2_historical_pg as bt

VERSION='2026-08-20 v24-motor2-base-candidate-features-v1'
START_DATE=os.getenv('MOTOR2_BASEFEAT_START_DATE','2025-07-01').strip()
END_DATE=os.getenv('MOTOR2_BASEFEAT_END_DATE','2026-08-19').strip()
UNIT=max(1,int(os.getenv('MOTOR2_BASEFEAT_UNIT_YEN','100')))
PROGRESS=max(1,int(os.getenv('MOTOR2_BASEFEAT_PROGRESS_EVERY','5000')))
MAX_RACES=max(0,int(os.getenv('MOTOR2_BASEFEAT_MAX_RACES','0')))

def st(): return {'bets':0,'hits':0,'inv':0,'ret':0}
def add(s,hit,pay):
    s['bets']+=1; s['inv']+=UNIT
    if hit: s['hits']+=1; s['ret']+=pay
def roi(s): return s['ret']/s['inv']*100 if s['inv'] else 0.0
def hr(s): return s['hits']/s['bets']*100 if s['bets'] else 0.0

def period(ds):
    if ds<'2026-03-01': return 'TRAIN'
    if ds<'2026-05-01': return 'VALID'
    if ds<'2026-07-01': return 'TEST'
    if ds<'2026-08-01': return 'OOS1'
    return 'OOS2'

def rankvals(entries):
    pairs=[]
    for e in entries:
        lane=bt.si(e.get('lane'),0); m=bt.valid_motor2(e.get('motor_place2_rate'))
        if 1<=lane<=6 and m is not None: pairs.append((lane,float(m)))
    pairs.sort(key=lambda x:(-x[1],x[0]))
    return ({lane:i for i,(lane,_) in enumerate(pairs,1)}, {lane:v for lane,v in pairs}, sum(v for _,v in pairs)/len(pairs))

def dbucket(x):
    if x>=10:return 'D10+'
    if x>=5:return 'D5_10'
    if x>=0:return 'D0_5'
    if x>=-5:return 'D-5_0'
    if x>=-10:return 'D-10_-5'
    return 'D<-10'

def abucket(x):
    if x>=45:return 'A45+'
    if x>=40:return 'A40_45'
    if x>=35:return 'A35_40'
    if x>=30:return 'A30_35'
    return 'A<30'

def main():
    if not os.getenv('DATABASE_URL'): raise RuntimeError('DATABASE_URL ãå¿è¦ã§ãã')
    print(f'â backtest_v24_motor2_base_candidate_features_pg.py VERSION {VERSION}',flush=True)
    print(f'PERIOD={START_DATE}..{END_DATE} BASE_FIXED=1 DB_UPDATE=0 LINE=0 BUY=0',flush=True)
    ra=START_DATE.replace('-',''); rb=bt.next_day(END_DATE).replace('-','')
    races=fetch_all('select race_id,race_date,venue_id,venue_code,race_no from v2_races where race_date >= %s and race_date <= %s order by race_date,venue_id,race_no',(START_DATE,END_DATE))
    entries=fetch_all('select race_id,lane,racer_class,national_win_rate,national_place2_rate,local_place2_rate,avg_st,motor_place2_rate from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane',(ra,rb))
    results=fetch_all("select race_id,trifecta_ticket,trifecta_payout_yen from v2_results where race_date >= %s and race_date <= %s and result_status='official' and race_status='official' and trifecta_ticket is not null and trifecta_payout_yen>0",(START_DATE,END_DATE))
    oddsrows=fetch_all('select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s and odds>0 order by race_id,ticket',(ra,rb))
    eb=defaultdict(list)
    for e in entries: eb[str(e.get('race_id') or '')].append(e)
    rbm={}
    for r in results:
        t=bt.norm_ticket(r.get('trifecta_ticket')); pay=bt.si(r.get('trifecta_payout_yen'),0)
        if t and pay>0: rbm[str(r.get('race_id'))]=(t,pay)
    ob=defaultdict(dict)
    for o in oddsrows:
        t=bt.norm_ticket(o.get('ticket')); odd=bt.sf(o.get('odds'),None)
        if t and odd and odd>0: ob[str(o.get('race_id'))][t]=float(odd)
    periods=('ALL','TRAIN','VALID','TEST','OOS1','OOS2')
    base={p:{k:st() for k in ('ALL','LOW','MID')} for p in periods}
    feats={p:{k:{f:defaultdict(st) for f in ('HEAD_RANK','BEST_RANK','TOP_CONTAIN','TICKET_AVG','AVG_DIFF','HEAD_DIFF')} for k in ('LOW','MID')} for p in periods}
    processed=se=sm=sr=so=cands=0
    for race in races:
        if MAX_RACES and processed>=MAX_RACES: break
        rid=str(race.get('race_id') or ''); ds=str(race.get('race_date') or '')[:10]
        if rid not in rbm: sr+=1; continue
        ent=eb.get(rid,[])
        if len(ent)!=6 or {bt.si(e.get('lane')) for e in ent}!={1,2,3,4,5,6}: se+=1; continue
        if sum(bt.valid_motor2(e.get('motor_place2_rate')) is not None for e in ent)!=6: sm+=1; continue
        odds=ob.get(rid,{})
        if not bt.validate_odds(odds): so+=1; continue
        venue=str(race.get('venue_id') or race.get('venue_code') or '').zfill(2)
        win,pay=rbm[rid]; mr=bt.rank_map(odds,reverse=False); pr=bt.rank_map(bt.ticket_probs(ent,venue,0.0),reverse=True)
        lows={t for t,o in odds.items() if bt.is_low(pr[t],mr[t],float(o))}
        mids={t for t,o in odds.items() if bt.is_mid(t,pr[t],mr[t],float(o))}
        rk,val,ravg=rankvals(ent); pp=period(ds)
        for kind,tickets in (('LOW',lows),('MID',mids)):
            for t in tickets:
                cands+=1; lanes=[int(x) for x in t.split('-')]; hit=t==win
                for p in ('ALL',pp): add(base[p]['ALL'],hit,pay); add(base[p][kind],hit,pay)
                rs=[rk[x] for x in lanes]; vs=[val[x] for x in lanes]
                contains='TOP1' if 1 in rs else 'TOP2' if any(x<=2 for x in rs) else 'TOP3' if any(x<=3 for x in rs) else 'NO_TOP3'
                fd={'HEAD_RANK':f'R{rs[0]}','BEST_RANK':f'R{min(rs)}','TOP_CONTAIN':contains,'TICKET_AVG':abucket(sum(vs)/3),'AVG_DIFF':dbucket(sum(vs)/3-ravg),'HEAD_DIFF':dbucket(vs[0]-ravg)}
                for p in ('ALL',pp):
                    for fn,b in fd.items(): add(feats[p][kind][fn][b],hit,pay)
        processed+=1
        if processed%PROGRESS==0: print(f'PROGRESS processed={processed} race_id={rid}',flush=True)
    print('=== BASE FIXED SUMMARY ===',flush=True)
    for p in periods:
        print(f'[{p}]',flush=True)
        for k in ('ALL','LOW','MID'):
            s=base[p][k]; print(f'  {k}: bets={s["bets"]} hits={s["hits"]} hit_rate={hr(s):.3f}% ROI={roi(s):.2f}%',flush=True)
    for kind in ('LOW','MID'):
        print(f'=== {kind} MOTOR2 FEATURE STABILITY ===',flush=True)
        for fn in ('HEAD_RANK','BEST_RANK','TOP_CONTAIN','TICKET_AVG','AVG_DIFF','HEAD_DIFF'):
            print(f'--- {fn} ---',flush=True)
            for b in sorted(feats['ALL'][kind][fn]):
                a=feats['ALL'][kind][fn][b]
                detail=[]
                for p in ('TRAIN','VALID','TEST','OOS1','OOS2'):
                    s=feats[p][kind][fn].get(b,st()); detail.append(f'{p}={s["bets"]}/{s["hits"]}/{roi(s):.1f}%')
                print(f'{b}: ALL={a["bets"]}/{a["hits"]}/{roi(a):.2f}% '+' '.join(detail),flush=True)
    print('=== AUDIT ===',flush=True)
    print(f'processed={processed}',flush=True); print(f'candidate_rows={cands}',flush=True)
    print(f'skipped_entries={se}',flush=True); print(f'skipped_motor2={sm}',flush=True); print(f'skipped_result={sr}',flush=True); print(f'skipped_odds={so}',flush=True); print('RESULT=PASS',flush=True)

if __name__=='__main__': main()