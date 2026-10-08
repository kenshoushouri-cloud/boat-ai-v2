# -*- coding: utf-8 -*-
"""V5 exhibition-time-rank forward validation using frozen first-write-wins shadow targets."""
from __future__ import annotations
import json, os
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any
from db_pg import fetch_all
import research.v5_lane_class_plus_exhibition_time_rank_pg as core

START=os.getenv("START_DATE","2025-07-01")
END=os.getenv("END_DATE","2026-10-05")
LABEL="historical"
TABLE="v2_bao_exhibition_shadow_snapshots"

def iso(v:Any)->str:
    if isinstance(v,datetime): return v.date().isoformat()
    if isinstance(v,date): return v.isoformat()
    return str(v)

def main():
    ex=fetch_all("select to_regclass('public.'||%s) tbl",(TABLE,))
    if not ex or not ex[0].get("tbl"):
        raise RuntimeError("forward shadow table unavailable")

    shadow=fetch_all(f"""
      select race_id,race_date,venue_id,captured_at,deadline_at,minutes_before,
             exhibition_time_ranks,source
      from {TABLE}
      where race_date between %s and %s
      order by race_date,race_id
    """,(START,END))
    if not shadow: raise RuntimeError("no forward shadow rows")

    safe={}
    unsafe=0
    for x in shadow:
        ranks=[int(v) for v in (x.get("exhibition_time_ranks") or [])]
        cap=x.get("captured_at"); dl=x.get("deadline_at"); mb=float(x.get("minutes_before") or -1)
        ok=(cap is not None and dl is not None and cap<dl and 8.0<=mb<=15.0
            and len(ranks)==6 and sorted(ranks)==[1,2,3,4,5,6]
            and str(x.get("source") or "")=="official_beforeinfo")
        if not ok:
            unsafe+=1; continue
        safe[str(x["race_id"])]={i+1:str(ranks[i]) for i in range(6)}

    target_ids=set(safe)
    target_dates={str(x["race_id"]):iso(x["race_date"]) for x in shadow if str(x["race_id"]) in target_ids}
    target_end=max(target_dates.values())

    rc,ec,xc,cc=core.cols("v2_races"),core.cols("v2_race_entries"),core.cols("v2_results"),core.cols("v2_realtime_exhibition_snapshots")
    we=core.winexpr(xc); ve=core.venueexpr(rc)
    fs=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc: fs.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc: fs.append("coalesce(rs.race_status,'official')='official'")

    races=fetch_all(f"""select r.race_id,r.race_date,{ve} venue,{we} winner
      from v2_races r join v2_results rs on rs.race_id=r.race_id
      where {' and '.join(fs)} order by r.race_date,r.race_id""",(START,target_end))
    es=fetch_all("""select e.race_id,e.lane,e.racer_class,c.exhibition_time_rank
      from v2_race_entries e
      join v2_races r on r.race_id=e.race_id
      left join v2_realtime_exhibition_snapshots c
        on c.race_id=e.race_id and c.lane=e.lane and c.snapshot_label=%s
      where r.race_date between %s and %s
      order by r.race_date,e.race_id,e.lane""",(LABEL,START,target_end))

    wb={str(r["race_id"]):int(r["winner"]) for r in races}
    db={str(r["race_id"]):iso(r["race_date"]) for r in races}
    vb={str(r["race_id"]):str(r["venue"]) for r in races}

    classes=defaultdict(dict); hist_rank=defaultdict(dict)
    for e in es:
        rid=str(e["race_id"])
        if rid not in wb: continue
        lane=core.ii(e["lane"]); cls=core.clean(e["racer_class"]); rk=core.stkey(e["exhibition_time_rank"])
        if lane not in range(1,7) or cls is None: continue
        classes[rid][lane]=cls
        if rk is not None: hist_rank[rid][lane]=rk

    hist_days=defaultdict(list)
    all_days=sorted(set(db.values()))
    for rid in wb:
        if len(classes[rid])==6 and len(hist_rank[rid])==6:
            hist_days[db[rid]].append(rid)

    target_days=defaultdict(list)
    missing_target=0
    for rid in sorted(target_ids):
        if rid not in wb or len(classes[rid])!=6:
            missing_target+=1; continue
        target_days[db[rid]].append(rid)

    lw=Counter();gn=0
    lc_s={i:Counter() for i in range(1,7)};lc_w={i:Counter() for i in range(1,7)}
    st_s=Counter();st_w=Counter()
    tot={"n":0,"bll":0.0,"bbr":0.0,"bh":0,"cll":0.0,"cbr":0.0,"ch":0,"seen":0,"obs":0,"ws":0.0}
    pv=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})
    pd=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})

    for day in all_days:
        lp=core.lane_probs(lw,gn)

        # Score frozen-forward targets first. No outcomes from this day have been added yet.
        for rid in target_days.get(day,[]):
            clsmap=classes[rid]
            bp=core.lc_probs(clsmap,lp,lc_s,lc_w)
            raw=[]
            for lane in range(1,7):
                key=(lane,clsmap[lane],safe[rid][lane])
                q,n,wt=core.adjusted(key,bp[lane-1],st_s,st_w)
                raw.append(max(q,core.EPS))
                tot["seen"]+=int(n>0);tot["obs"]+=1;tot["ws"]+=wt
            s=sum(raw); cp=[x/s for x in raw]; winner=wb[rid]
            bll,bbr,bh=core.score(bp,winner); cll,cbr,ch=core.score(cp,winner)
            tot["n"]+=1;tot["bll"]+=bll;tot["bbr"]+=bbr;tot["bh"]+=bh
            tot["cll"]+=cll;tot["cbr"]+=cbr;tot["ch"]+=ch
            for z in (pv[vb[rid]],pd[day]):
                z["n"]+=1;z["bll"]+=bll;z["bbr"]+=bbr;z["cll"]+=cll;z["cbr"]+=cbr

        # Only after scoring the day, update histories from mutable historical rows.
        dlw=Counter();dlcs={i:Counter() for i in range(1,7)};dlcw={i:Counter() for i in range(1,7)}
        dss=Counter();dsw=Counter()
        for rid in hist_days.get(day,[]):
            winner=wb[rid]; clsmap=classes[rid]
            dlw[winner]+=1
            for lane in range(1,7):
                cls=clsmap[lane]; rk=hist_rank[rid][lane]
                dlcs[lane][cls]+=1; dss[(lane,cls,rk)]+=1
            wcls=clsmap[winner]; wrk=hist_rank[rid][winner]
            dlcw[winner][wcls]+=1; dsw[(winner,wcls,wrk)]+=1
        lw.update(dlw); gn+=sum(dlw.values())
        for lane in range(1,7):
            lc_s[lane].update(dlcs[lane]); lc_w[lane].update(dlcw[lane])
        st_s.update(dss); st_w.update(dsw)

    n=tot["n"]
    if not n: raise RuntimeError("zero forward scoreable races")
    bll=tot["bll"]/n;bbr=tot["bbr"]/n;cll=tot["cll"]/n;cbr=tot["cbr"]/n
    vll=vbr=0; vdll={};vdbr={}
    for v,z in sorted(pv.items()):
        vn=z["n"];dll=z["cll"]/vn-z["bll"]/vn;dbr=z["cbr"]/vn-z["bbr"]/vn
        vdll[v]=dll;vdbr[v]=dbr;vll+=dll<0;vbr+=dbr<0
    day_metrics={}
    for ds,z in sorted(pd.items()):
        dn=z["n"]; day_metrics[ds]={
          "races":dn,
          "delta_logloss":z["cll"]/dn-z["bll"]/dn,
          "delta_brier":z["cbr"]/dn-z["bbr"]/dn
        }

    out={
      "contract":"V5_EXHIBITION_TIME_RANK_FROZEN_FORWARD_V1",
      "train_start":START,"target_end":target_end,
      "target":{"source":"v2_bao_exhibition_shadow_snapshots","first_write_wins":True,
                "window_minutes":[8,15],"official_beforeinfo_only":True,
                "unsafe_rows_excluded":unsafe,"missing_target_rows":missing_target},
      "coverage":{"shadow_rows":len(shadow),"safe_shadow_rows":len(safe),"scored":n,
                  "seen_cell_pct":100*tot["seen"]/tot["obs"] if tot["obs"] else None,
                  "mean_shrink_weight":tot["ws"]/tot["obs"] if tot["obs"] else None,
                  "target_dates":len(pd),"target_venues":len(pv)},
      "metrics":{"baseline_logloss":bll,"candidate_logloss":cll,"delta_logloss":cll-bll,
                 "baseline_brier":bbr,"candidate_brier":cbr,"delta_brier":cbr-bbr,
                 "baseline_top1":tot["bh"]/n,"candidate_top1":tot["ch"]/n,
                 "venues_better_logloss":vll,"venues_better_brier":vbr},
      "day_metrics":day_metrics,"venue_delta_logloss":vdll,"venue_delta_brier":vdbr,
      "safety":{"db_write":False,"same_day_results_used":False,"production_model_change":False,
                "line_change":False,"purchase_change":False,"stake_change":False}
    }
    print("V5_EXHIBITION_TIME_RANK_FROZEN_FORWARD_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
