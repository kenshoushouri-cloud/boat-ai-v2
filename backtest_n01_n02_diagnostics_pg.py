# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24
import collect_candidate_filter_shadow_pg as shadow

VERSION="2026-08-18 n01-n02-diagnostics-v1"
START_DATE=os.getenv("BACKTEST_START_DATE","2025-07-01")
END_DATE=os.getenv("BACKTEST_END_DATE","2026-08-16")
UNIT_YEN=max(1,int(os.getenv("BACKTEST_UNIT_YEN","100")))
PROGRESS_EVERY_DAYS=max(1,int(os.getenv("BACKTEST_PROGRESS_EVERY_DAYS","10")))

RULES_BY_ID={str(r["rule_id"]).upper():r for r in shadow.RULES}
ACTIVE_RULES=[RULES_BY_ID["N01"],RULES_BY_ID["N02"]]

def _si(v:Any,d:int=0)->int:
    try:return int(float(v))
    except:return d

def _sf(v:Any,d:float=0.0)->float:
    try:return float(v)
    except:return d

def _dates(a:str,b:str)->Iterable[str]:
    d=datetime.strptime(a,"%Y-%m-%d"); e=datetime.strptime(b,"%Y-%m-%d")
    while d<=e:
        yield d.strftime("%Y-%m-%d"); d+=timedelta(days=1)

def _stat()->Dict[str,Any]:
    return {"bets":0,"hits":0,"investment":0,"return":0,"hit_returns":[]}

def _add(s:Dict[str,Any],hit:bool,payout:int):
    s["bets"]+=1; s["investment"]+=UNIT_YEN
    if hit:
        s["hits"]+=1; s["return"]+=payout
        if payout>0:s["hit_returns"].append(payout)

def _print(label:str,s:Dict[str,Any]):
    b=s["bets"]; h=s["hits"]; inv=s["investment"]; ret=s["return"]
    hr=h/b*100 if b else 0
    roi=ret/inv*100 if inv else 0
    mx=max(s["hit_returns"]) if s["hit_returns"] else 0
    sh=mx/ret*100 if ret else 0
    print(f"{label}: bets={b} hits={h} hit_rate={hr:.3f}% investment={inv} return={ret} profit={ret-inv} ROI={roi:.2f}% max_hit={mx} single_hit_share={sh:.2f}%",flush=True)

def _fetch_day(ds:str):
    p=ds.replace("-","")
    np=(datetime.strptime(ds,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y%m%d")
    results=fetch_all("""
      select race_id,trifecta_ticket,trifecta_payout_yen
      from v2_results
      where race_date=%s
        and trifecta_ticket is not null
        and trifecta_payout_yen is not null
        and trifecta_payout_yen>0
        and finish_order is not null
        and winning_method is not null
        and coalesce(result_status,'')='official'
        and coalesce(race_status,'')='official'
      order by race_id
    """,(ds,))
    rb={str(r["race_id"]):r for r in results if r.get("race_id")}
    ids=set(rb)
    if not ids:return [],{},{},{},{}
    races=[r for r in fetch_all("select * from v2_races where race_date=%s order by venue_id,race_no",(ds,)) if str(r.get("race_id") or "") in ids]
    entries=fetch_all("""
      select race_id,lane,racer_number,racer_class,racer_name,
             national_win_rate,national_place2_rate,local_win_rate,local_place2_rate,
             motor_no,boat_no,avg_st
      from v2_race_entries
      where race_id >= %s and race_id < %s
      order by race_id,lane
    """,(p,np))
    eb=defaultdict(list)
    for r in entries:
        rid=str(r.get("race_id") or "")
        if rid in ids:eb[rid].append(r)
    ob=defaultdict(dict)
    for r in fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s order by race_id,ticket",(p,np)):
        rid=str(r.get("race_id") or "")
        if rid not in ids:continue
        t=v24._norm_ticket(r.get("ticket")); odd=_sf(r.get("odds"))
        if t and odd>0:ob[rid][t]=odd
    kc={}
    for r in fetch_all("select race_id,count(*)::int as n from v2_result_entries where race_id >= %s and race_id < %s group by race_id",(p,np)):
        kc[str(r.get("race_id"))]=_si(r.get("n"))
    return races,eb,ob,rb,kc

def main():
    print(f"â backtest_n01_n02_diagnostics_pg.py VERSION {VERSION}",flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE} UNIT_YEN={UNIT_YEN}",flush=True)
    print("DBæ¸ãè¾¼ã¿ãªããLINEéç¥ãªãã",flush=True)
    if not os.getenv("DATABASE_URL"):raise RuntimeError("DATABASE_URL ãå¿è¦ã§ã")

    overall=defaultdict(_stat); month=defaultdict(_stat); venue=defaultdict(_stat)
    race_no_s=defaultdict(_stat); pr_s=defaultdict(_stat); mr_s=defaultdict(_stat)
    odds_s=defaultdict(_stat); head_s=defaultdict(_stat)
    ready=0; sels=0
    ds=list(_dates(START_DATE,END_DATE))

    for i,day in enumerate(ds,1):
        races,eb,ob,rb,kc=_fetch_day(day)
        for race in races:
            rid=str(race.get("race_id") or "")
            vid=str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            rno=_si(race.get("race_no"))
            entries=eb.get(rid,[])
            if len(v24._entry_by_lane(entries))!=6 or kc.get(rid,0)!=6:continue
            odds=ob.get(rid,{})
            ok,_=v24._validate_odds_snapshot(odds)
            if len(odds)!=120 or not ok:continue
            ready+=1
            res=rb[rid]; rt=v24._norm_ticket(res.get("trifecta_ticket")); payout=_si(res.get("trifecta_payout_yen"))
            meta=v24._metadata_text(race); vs=v24._infer_venue_style(vid); ec=v24._infer_event_category(meta)
            ranked=v24._rank_candidates(entries,vid,odds)

            for rule in ACTIVE_RULES:
                rid_rule=str(rule["rule_id"])
                if rno not in rule["race_nos"]:continue
                if rule["venue_style"]!="ALL" and vs!=rule["venue_style"]:continue
                if rule["event_category"]!="ALL" and ec!=rule["event_category"]:continue
                matches=[x for x in ranked if shadow._match_rule(x,rule)]
                sel=shadow._select_one(matches,str(rule["select_mode"]))
                if not sel:continue
                ticket=str(sel.get("ticket") or "")
                if not ticket:continue
                hit=ticket==rt; sels+=1
                pr=_si(sel.get("prob_rank"),999); mr=_si(sel.get("market_rank"),999); odd=_sf(sel.get("odds"))
                head=ticket.split("-")[0] if "-" in ticket else "?"
                bucket="3.0-3.9" if 3<=odd<4 else "4.0-4.9" if 4<=odd<5 else "5.0-5.9" if 5<=odd<6 else "other"
                for s in (
                    overall[rid_rule],month[(rid_rule,day[:7])],venue[(rid_rule,vid)],
                    race_no_s[(rid_rule,rno)],pr_s[(rid_rule,pr)],mr_s[(rid_rule,mr)],
                    odds_s[(rid_rule,bucket)],head_s[(rid_rule,head)]
                ): _add(s,hit,payout)
        if i%PROGRESS_EVERY_DAYS==0 or i==len(ds):
            print(f"PROGRESS {i}/{len(ds)} date={day} ready_races={ready} selections={sels}",flush=True)

    print("\\n=== OVERALL ===",flush=True)
    for r in ("N01","N02"):_print(r,overall[r])

    print("\\n=== RULE x RACE_NO ===",flush=True)
    for r in ("N01","N02"):
        for n in range(1,13):
            s=race_no_s.get((r,n))
            if s and s["bets"]:_print(f"{r} R{n:02d}",s)

    print("\\n=== RULE x PROB_RANK ===",flush=True)
    for r in ("N01","N02"):
        for pr in sorted(x for (rr,x) in pr_s if rr==r):_print(f"{r} pr={pr}",pr_s[(r,pr)])

    print("\\n=== RULE x MARKET_RANK ===",flush=True)
    for r in ("N01","N02"):
        for mr in sorted(x for (rr,x) in mr_s if rr==r):_print(f"{r} mr={mr}",mr_s[(r,mr)])

    print("\\n=== RULE x ODDS_BUCKET ===",flush=True)
    for r in ("N01","N02"):
        for b in ("3.0-3.9","4.0-4.9","5.0-5.9","other"):
            s=odds_s.get((r,b))
            if s and s["bets"]:_print(f"{r} odds={b}",s)

    print("\\n=== RULE x HEAD_LANE ===",flush=True)
    for r in ("N01","N02"):
        for lane in ("1","2","3","4","5","6"):
            s=head_s.get((r,lane))
            if s and s["bets"]:_print(f"{r} head={lane}",s)

    print("\\n=== RULE x VENUE ===",flush=True)
    for r in ("N01","N02"):
        for v in sorted(x for (rr,x) in venue if rr==r):_print(f"{r} venue={v}",venue[(r,v)])

    print("\\n=== RULE x MONTH ===",flush=True)
    for r in ("N01","N02"):
        for m in sorted(x for (rr,x) in month if rr==r):_print(f"{r} {m}",month[(r,m)])

    print("\\n=== IMPORTANT NOTE ===",flush=True)
    print("N01/N02ã®æ¡ä»¶ã¯å¤æ´ãããé¸æå¾ã®å®ç¸¾ãåè§£ãã¦ãã¾ããé«ROIã®ç´°åºåãå³ã«ã¼ã«åãããä»¶æ°ã»æå¥åç¾æ§ã»æéåå²ã§åæ¤è¨¼ãã¦ãã ããã",flush=True)
    print("RESULT=PASS",flush=True)

if __name__=="__main__":
    main()