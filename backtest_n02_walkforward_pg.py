# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List
from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24
import collect_candidate_filter_shadow_pg as shadow

VERSION="2026-08-18 n02-walkforward-dd-v1"
START_DATE=os.getenv("BACKTEST_START_DATE","2025-07-01")
END_DATE=os.getenv("BACKTEST_END_DATE","2026-08-16")
UNIT=max(1,int(os.getenv("BACKTEST_UNIT_YEN","100")))
BLOCKS=max(2,int(os.getenv("BACKTEST_WALKFORWARD_BLOCKS","4")))
PROGRESS=max(1,int(os.getenv("BACKTEST_PROGRESS_EVERY_DAYS","10")))
N02={str(r["rule_id"]).upper():r for r in shadow.RULES}["N02"]

def si(v,d=0):
    try:return int(float(v))
    except:return d
def sf(v,d=0.0):
    try:return float(v)
    except:return d
def dates(a,b):
    d=datetime.strptime(a,"%Y-%m-%d"); e=datetime.strptime(b,"%Y-%m-%d")
    while d<=e:
        yield d.strftime("%Y-%m-%d"); d+=timedelta(days=1)

def fetch_day(ds):
    p=ds.replace("-",""); np=(datetime.strptime(ds,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y%m%d")
    results=fetch_all("""select race_id,trifecta_ticket,trifecta_payout_yen from v2_results
      where race_date=%s and trifecta_ticket is not null and trifecta_payout_yen>0
      and finish_order is not null and winning_method is not null
      and coalesce(result_status,'')='official' and coalesce(race_status,'')='official'
      order by race_id""",(ds,))
    rb={str(r["race_id"]):r for r in results if r.get("race_id")}; ids=set(rb)
    if not ids:return [],{},{},{},{}
    races=[r for r in fetch_all("select * from v2_races where race_date=%s order by venue_id,race_no",(ds,)) if str(r.get("race_id") or "") in ids]
    eb=defaultdict(list)
    for r in fetch_all("""select race_id,lane,racer_number,racer_class,racer_name,
      national_win_rate,national_place2_rate,local_win_rate,local_place2_rate,motor_no,boat_no,avg_st
      from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane""",(p,np)):
        rid=str(r.get("race_id") or "")
        if rid in ids:eb[rid].append(r)
    ob=defaultdict(dict)
    for r in fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s order by race_id,ticket",(p,np)):
        rid=str(r.get("race_id") or "")
        if rid in ids:
            t=v24._norm_ticket(r.get("ticket")); o=sf(r.get("odds"))
            if t and o>0:ob[rid][t]=o
    kc={}
    for r in fetch_all("select race_id,count(*)::int n from v2_result_entries where race_id >= %s and race_id < %s group by race_id",(p,np)):
        kc[str(r.get("race_id"))]=si(r.get("n"))
    return races,eb,ob,rb,kc

def stats(rows):
    b=len(rows); h=sum(x["hit"] for x in rows); inv=b*UNIT; ret=sum(x["ret"] for x in rows)
    streak=mxst=0; equity=peak=0; maxdd=0; peak_i=0; maxdd_bets=0
    for i,x in enumerate(rows,1):
        streak=0 if x["hit"] else streak+1; mxst=max(mxst,streak)
        equity+=x["ret"]-UNIT
        if equity>peak: peak=equity; peak_i=i
        dd=peak-equity
        if dd>maxdd:maxdd=dd; maxdd_bets=i-peak_i
    return dict(bets=b,hits=h,hit_rate=h/b*100 if b else 0,investment=inv,ret=ret,
                profit=ret-inv,roi=ret/inv*100 if inv else 0,max_streak=mxst,
                maxdd=maxdd,maxdd_bets=maxdd_bets)
def show(label,rows):
    s=stats(rows)
    print(f"{label}: bets={s['bets']} hits={s['hits']} hit_rate={s['hit_rate']:.3f}% investment={s['investment']} return={s['ret']} profit={s['profit']} ROI={s['roi']:.2f}% max_losing_streak={s['max_streak']} max_drawdown={s['maxdd']} max_drawdown_bets={s['maxdd_bets']}",flush=True)

def main():
    print(f"â backtest_n02_walkforward_pg.py VERSION {VERSION}",flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE} UNIT_YEN={UNIT} BLOCKS={BLOCKS}",flush=True)
    print("N02æ¡ä»¶å¤æ´ãªããDBæ¸ãè¾¼ã¿ãªããLINEéç¥ãªãã",flush=True)
    if not os.getenv("DATABASE_URL"):raise RuntimeError("DATABASE_URL ãå¿è¦ã§ã")
    rec=[]; ready=0; ds=list(dates(START_DATE,END_DATE))
    for i,day in enumerate(ds,1):
        races,eb,ob,rb,kc=fetch_day(day)
        for race in races:
            rid=str(race.get("race_id") or ""); vid=str(race.get("venue_id") or race.get("venue_code") or "").zfill(2); rno=si(race.get("race_no"))
            entries=eb.get(rid,[])
            if len(v24._entry_by_lane(entries))!=6 or kc.get(rid,0)!=6:continue
            odds=ob.get(rid,{}); ok,_=v24._validate_odds_snapshot(odds)
            if len(odds)!=120 or not ok:continue
            ready+=1
            vs=v24._infer_venue_style(vid); ec=v24._infer_event_category(v24._metadata_text(race))
            if rno not in N02["race_nos"]:continue
            if N02["venue_style"]!="ALL" and vs!=N02["venue_style"]:continue
            if N02["event_category"]!="ALL" and ec!=N02["event_category"]:continue
            ranked=v24._rank_candidates(entries,vid,odds)
            sel=shadow._select_one([x for x in ranked if shadow._match_rule(x,N02)],str(N02["select_mode"]))
            if not sel:continue
            ticket=str(sel.get("ticket") or "")
            if not ticket:continue
            res=rb[rid]; rt=v24._norm_ticket(res.get("trifecta_ticket")); payout=si(res.get("trifecta_payout_yen"))
            hit=ticket==rt
            rec.append({"date":day,"race_id":rid,"hit":hit,"ret":payout if hit else 0})
        if i%PROGRESS==0 or i==len(ds):
            print(f"PROGRESS {i}/{len(ds)} date={day} ready_races={ready} selections={len(rec)}",flush=True)
    rec.sort(key=lambda x:(x["date"],x["race_id"]))
    print("\n=== N02 OVERALL ===",flush=True); show("N02 ALL",rec)
    print("\n=== N02 WALK-FORWARD BLOCKS ===",flush=True)
    n=len(rec); base=n//BLOCKS; rem=n%BLOCKS; pos=0; rois=[]
    for b in range(BLOCKS):
        size=base+(1 if b<rem else 0); block=rec[pos:pos+size]; pos+=size
        if not block:continue
        show(f"BLOCK{b+1} {block[0]['date']}..{block[-1]['date']}",block); rois.append(stats(block)["roi"])
    print("\n=== WALK-FORWARD SUMMARY ===",flush=True)
    print(f"profitable_blocks={sum(x>=100 for x in rois)}/{len(rois)}",flush=True)
    if rois:print(f"min_block_roi={min(rois):.2f}% max_block_roi={max(rois):.2f}% avg_block_roi={sum(rois)/len(rois):.2f}%",flush=True)
    s=stats(rec)
    print("\n=== RISK SUMMARY ===",flush=True)
    print(f"max_losing_streak={s['max_streak']}",flush=True)
    print(f"max_drawdown_yen={s['maxdd']}",flush=True)
    print(f"max_drawdown_bets={s['maxdd_bets']}",flush=True)
    print("RESULT=PASS",flush=True)
if __name__=="__main__":main()