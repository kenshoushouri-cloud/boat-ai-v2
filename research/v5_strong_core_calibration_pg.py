# -*- coding: utf-8 -*-
"""V5 strong-core train-only temperature calibration, fixed-weight OOS evaluation."""
from __future__ import annotations
import json,math,os
from collections import Counter,defaultdict
from research import v5_lc_rf_exrank_rc_plus_opponent_pg as b
from research import v5_lane_class_plus_venue_residual_pg as vr
from db_pg import fetch_all

START=os.getenv("START_DATE","2025-07-01")
END=os.getenv("END_DATE","2026-10-05")
TRAIN_END="2026-03-31"
VALID_END="2026-04-30"
OOS1_END="2026-05-31"
TEMPS=(0.80,0.90,1.00,1.10,1.20,1.30)
W={"recent_form":0.50,"exhibition_rank":1.00,"racer_course":0.75,"opponent":1.25,"venue_lane":0.75}
EPS=1e-12

def weighted_probs(row):
    raw=[]
    for i in range(6):
        x=max(row["base"][i],EPS)
        for f,w in W.items():
            x*=max(row["factors"][f][i],EPS)**w
        raw.append(max(x,EPS))
    s=sum(raw);return [x/s for x in raw]

def temp_probs(p,t):
    raw=[max(x,EPS)**(1.0/t) for x in p]
    s=sum(raw);return [x/s for x in raw]

def ece10(rows,t):
    bins=[{"n":0,"psum":0.0,"ysum":0.0} for _ in range(10)]
    total=0
    for r in rows:
        p=temp_probs(weighted_probs(r),t)
        for i,x in enumerate(p):
            k=min(9,int(x*10))
            z=bins[k];z["n"]+=1;z["psum"]+=x;z["ysum"]+=1.0 if (i+1)==r["winner"] else 0.0
            total+=1
    e=0.0
    for z in bins:
        if not z["n"]:continue
        e+=(z["n"]/total)*abs(z["psum"]/z["n"]-z["ysum"]/z["n"])
    return e

def metrics(rows,t):
    n=0;ll=br=hit=0.0
    for r in rows:
        p=temp_probs(weighted_probs(r),t)
        a,c,h=b.score(p,r["winner"])
        n+=1;ll+=a;br+=c;hit+=h
    return {"n":n,"logloss":ll/n,"brier":br/n,"top1":hit/n,"ece10":ece10(rows,t)}

def main():
    rc,ec,xc,cc,rec=b.cols("v2_races"),b.cols("v2_race_entries"),b.cols("v2_results"),b.cols("v2_realtime_exhibition_snapshots"),b.cols("v2_result_entries")
    if {"lane","racer_number","racer_class","recent_form"}-ec:raise RuntimeError("missing entry columns")
    if {"race_id","lane","exhibition_time_rank"}-cc:raise RuntimeError("missing exhibition columns")
    if {"racer_number","start_course","finish_position"}-rec:raise RuntimeError("missing result history columns")
    we=b.winexpr(xc);ve=b.venueexpr(rc)
    fs=["r.race_date >= %s","r.race_date <= %s",f"({we}) between 1 and 6"]
    if "result_status" in xc:fs.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in xc:fs.append("coalesce(rs.race_status,'official')='official'")
    races=fetch_all(f"""select r.race_id,r.race_date,{ve} venue,{we} winner
      from v2_races r join v2_results rs on rs.race_id=r.race_id
      where {' and '.join(fs)} order by r.race_date,r.race_id""",(START,END))
    es=fetch_all("""select e.race_id,e.lane,e.racer_number,e.racer_class,e.recent_form,x.exhibition_time_rank
      from v2_race_entries e join v2_races r on r.race_id=e.race_id
      left join v2_realtime_exhibition_snapshots x
        on x.race_id=e.race_id and x.lane=e.lane and x.snapshot_label=%s
      where r.race_date between %s and %s order by e.race_id,e.lane""",(b.LABEL,START,END))
    hist=fetch_all("""select re.racer_number,re.start_course,re.finish_position,r.race_date::date race_date
      from v2_result_entries re join v2_races r on r.race_id=re.race_id
      where r.race_date between %s and %s and re.racer_number is not null
      order by r.race_date,re.race_id,re.lane""",(START,END))

    wb={str(r["race_id"]):int(r["winner"]) for r in races}
    db={str(r["race_id"]):b.iso(r["race_date"]) for r in races};vb={str(r["race_id"]):str(r["venue"]) for r in races}
    by=defaultdict(dict);invalid=0
    for e in es:
        rid=str(e["race_id"])
        if rid not in wb:continue
        lane=b.ii(e["lane"]);racer=b.ii(e["racer_number"]);cls=b.clean(e["racer_class"]);rk=b.rankkey(e["exhibition_time_rank"])
        rs,nvalid=b.recent_strength(e["recent_form"])
        if lane not in range(1,7) or racer<=0 or cls is None or rk is None:invalid+=1;continue
        by[rid][lane]=(racer,cls,rs,nvalid,rk)
    days=defaultdict(list);skip=0
    for rid in wb:
        if len(by[rid])==6 and all(i in by[rid] for i in range(1,7)):days[db[rid]].append(rid)
        else:skip+=1

    hday=defaultdict(list);badh=0
    for h in hist:
        racer=b.ii(h["racer_number"]);c=b.ii(h["start_course"]);f=b.ii(h["finish_position"])
        if racer<=0 or c not in range(1,7) or f not in range(1,7):badh+=1;continue
        hday[b.iso(h["race_date"])].append((racer,c,f))

    lw=Counter();gn=0
    lcs={i:Counter() for i in range(1,7)};lcw={i:Counter() for i in range(1,7)}
    rks=Counter();rkw=Counter()
    cs=Counter();ct=Counter();rcs={i:Counter() for i in range(1,7)};rct={i:Counter() for i in range(1,7)}
    ps=Counter();pw=Counter();vc=defaultdict(Counter);vn=Counter()
    rows=[]

    for day in sorted(days):
        gp=b.lane_probs(lw,gn);priors={c:b.rc_prior(c,cs,ct) for c in range(1,7)}
        dlw=Counter();dlcs={i:Counter() for i in range(1,7)};dlcw={i:Counter() for i in range(1,7)}
        drks=Counter();drkw=Counter();dps=Counter();dpw=Counter();dvc=defaultdict(Counter)
        for rid in days[day]:
            classes={l:by[rid][l][1] for l in range(1,7)}
            lcp=b.lc_probs(classes,gp,lcs,lcw)
            rf=[max(by[rid][l][2]/b.NEUTRAL,EPS) for l in range(1,7)]
            ex=[];rcf=[]
            for l in range(1,7):
                cls=by[rid][l][1];rk=by[rid][l][4]
                q,_,_=b.adjusted((l,cls,rk),lcp[l-1],rks,rkw)
                ex.append(max(q/max(lcp[l-1],EPS),EPS))
                racer=by[rid][l][0];rq,_,_=b.rc_adjusted(racer,l,priors[l],rcs,rct)
                rcf.append(max(rq/max(priors[l],EPS),EPS))
            opp_lc,_,_=b.opponent_probs(classes,lcp,ps,pw)
            opp=[max(opp_lc[i]/max(lcp[i],EPS),EPS) for i in range(6)]
            vp,_=vr.venue_shrunk(vb[rid],gp,vc,vn)
            vf=[max(vp[i]/max(gp[i],EPS),EPS) for i in range(6)]
            rows.append({"date":day,"venue":vb[rid],"winner":wb[rid],"base":lcp,
                         "factors":{"recent_form":rf,"exhibition_rank":ex,"racer_course":rcf,"opponent":opp,"venue_lane":vf}})

            winner=wb[rid];dlw[winner]+=1;dvc[vb[rid]][winner]+=1
            for l in range(1,7):
                cls=by[rid][l][1];rk=by[rid][l][4];dlcs[l][cls]+=1;drks[(l,cls,rk)]+=1
            wcls=by[rid][winner][1];wrk=by[rid][winner][4];dlcw[winner][wcls]+=1;drkw[(winner,wcls,wrk)]+=1
            for l in range(1,7):
                for o in range(1,7):
                    if o==l:continue
                    key=(l,classes[l],o,classes[o]);dps[key]+=1
                    if l==winner:dpw[key]+=1

        lw.update(dlw);gn+=sum(dlw.values())
        for l in range(1,7):lcs[l].update(dlcs[l]);lcw[l].update(dlcw[l])
        rks.update(drks);rkw.update(drkw);ps.update(dps);pw.update(dpw)
        for v,cnt in dvc.items():vc[v].update(cnt);vn[v]+=sum(cnt.values())
        for racer,c,f in hday.get(day,[]):
            cs[c]+=1;rcs[c][racer]+=1
            if f<=3:ct[c]+=1;rct[c][racer]+=1

    train=[r for r in rows if r["date"]<=TRAIN_END]
    oos=[r for r in rows if r["date"]>TRAIN_END]
    apr=[r for r in rows if TRAIN_END<r["date"]<=VALID_END]
    may=[r for r in rows if VALID_END<r["date"]<=OOS1_END]
    late=[r for r in rows if r["date"]>OOS1_END]

    train_scores={str(t):metrics(train,t) for t in TEMPS}
    base=train_scores["1.0"]
    eligible=[]
    for t in TEMPS:
        m=train_scores[str(t)]
        if m["logloss"]<=base["logloss"]+1e-12 and m["brier"]<=base["brier"]+1e-12:
            eligible.append((m["logloss"],m["brier"],m["ece10"],abs(t-1.0),t))
    selected=min(eligible)[-1] if eligible else 1.0

    def block(rs):
        return {"uncalibrated":metrics(rs,1.0),"calibrated":metrics(rs,selected)}
    vgll=vgbr=vgece=0;vd={}
    for v in sorted(set(r["venue"] for r in oos)):
        rr=[r for r in oos if r["venue"]==v];a=metrics(rr,1.0);c=metrics(rr,selected)
        dll=c["logloss"]-a["logloss"];dbr=c["brier"]-a["brier"];de=c["ece10"]-a["ece10"]
        vd[v]={"delta_logloss":dll,"delta_brier":dbr,"delta_ece10":de}
        vgll+=dll<0;vgbr+=dbr<0;vgece+=de<0

    out={"contract":"V5_STRONG_CORE_TRAIN_ONLY_TEMPERATURE_CALIBRATION_V1",
      "period":{"start":START,"end":END,"train_end":TRAIN_END,"april_end":VALID_END,"may_end":OOS1_END},
      "fixed_weights":W,
      "method":{"temperature_grid":list(TEMPS),"selected_temperature":selected,
                "formula":"p_cal proportional to p^(1/T)",
                "selection":"TRAIN only; eligible T must not worsen either LogLoss or Brier vs T=1, then lowest LogLoss",
                "oos_temperature_frozen":True,"parameter_selection_uses_oos":False,"same_day_results_used":False},
      "coverage":{"completed_races":len(races),"scored":len(rows),"coverage_pct":100*len(rows)/len(races),"skipped":skip,
                  "invalid_entry_rows":invalid,"invalid_history_rows":badh,"venue_count":len(set(r["venue"] for r in rows))},
      "train_grid":train_scores,
      "metrics":{"train":block(train),"oos_all":block(oos),"oos_april":block(apr),"oos_may":block(may),"oos_june_to_end":block(late),
                 "oos_venues_better_logloss":vgll,"oos_venues_better_brier":vgbr,"oos_venues_better_ece10":vgece},
      "oos_venue_delta":vd,
      "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False,"stake_change":False}}
    print("V5_STRONG_CORE_CALIBRATION_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
