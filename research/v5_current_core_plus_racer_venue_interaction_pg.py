# -*- coding: utf-8 -*-
"""V5 limited interaction: racer x venue prior-top3 residual over current strong core."""
from __future__ import annotations
import json,os
from collections import Counter,defaultdict
from research import v5_lc_rf_exrank_rc_plus_opponent_pg as b
from research import v5_lane_class_plus_venue_residual_pg as vr
from db_pg import fetch_all

START=os.getenv("START_DATE","2025-07-01"); END=os.getenv("END_DATE","2026-10-05")

def rv_prior(v,starts,top3):
    return (top3[v]+1.0)/(starts[v]+2.0)
def rv_adjusted(racer,v,prior,starts,top3):
    vals=[];svars=[]
    for rr,n in starts[v].items():
        if n<=0: continue
        r=(top3[v][rr]+2*prior)/(n+2)
        vals.append(r);svars.append(max(r*(1-r)/n,b.EPS))
    tau=0.0
    if len(vals)>=2:
        m=sum(vals)/len(vals)
        tau=max(0.0,sum((x-m)**2 for x in vals)/(len(vals)-1)-sum(svars)/len(svars))
    n=starts[v][racer];r=(top3[v][racer]+2*prior)/(n+2)
    if n<=0 or tau<=0:return prior,n,0.0
    wt=tau/(tau+max(r*(1-r)/n,b.EPS))
    return wt*r+(1-wt)*prior,n,wt

def main():
    rc,ec,xc,cc,rec=b.cols("v2_races"),b.cols("v2_race_entries"),b.cols("v2_results"),b.cols("v2_realtime_exhibition_snapshots"),b.cols("v2_result_entries")
    if {"lane","racer_number","racer_class","recent_form"}-ec: raise RuntimeError("missing entry columns")
    if {"race_id","lane","exhibition_time_rank"}-cc: raise RuntimeError("missing exhibition columns")
    if {"racer_number","start_course","finish_position"}-rec: raise RuntimeError("missing result history columns")
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
    hist=fetch_all(f"""select re.racer_number,re.start_course,re.finish_position,r.race_date::date race_date,{ve} venue
      from v2_result_entries re join v2_races r on r.race_id=re.race_id
      where r.race_date between %s and %s and re.racer_number is not null
      order by r.race_date,re.race_id,re.lane""",(START,END))

    wb={str(r["race_id"]):int(r["winner"]) for r in races}
    db={str(r["race_id"]):b.iso(r["race_date"]) for r in races}; vb={str(r["race_id"]):str(r["venue"]) for r in races}
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
        racer=b.ii(h["racer_number"]);c=b.ii(h["start_course"]);f=b.ii(h["finish_position"]);v=str(h["venue"])
        if racer<=0 or c not in range(1,7) or f not in range(1,7) or v=="NA":
            badh+=1;continue
        hday[b.iso(h["race_date"])].append((racer,c,f,v))

    lw=Counter();gn=0
    lcs={i:Counter() for i in range(1,7)};lcw={i:Counter() for i in range(1,7)}
    rks=Counter();rkw=Counter()
    cs=Counter();ct=Counter();rcs={i:Counter() for i in range(1,7)};rct={i:Counter() for i in range(1,7)}
    ps=Counter();pw=Counter();vc=defaultdict(Counter);vn=Counter()
    rvs=defaultdict(Counter);rvt=defaultdict(Counter);vs=Counter();vt=Counter()

    tot={"n":0,"bll":0.0,"bbr":0.0,"bh":0,"cll":0.0,"cbr":0.0,"ch":0,
         "rvobs":0,"rvnoprior":0,"rvws":0.0,"vws":0.0,"vwn":0}
    pv=defaultdict(lambda:{"n":0,"bll":0.0,"bbr":0.0,"cll":0.0,"cbr":0.0})

    for day in sorted(days):
        gp=b.lane_probs(lw,gn);cpri={c:b.rc_prior(c,cs,ct) for c in range(1,7)}
        vpri={v:rv_prior(v,vs,vt) for v in set(list(vs.keys())+[vb[r] for r in days[day]])}
        dlw=Counter();dlcs={i:Counter() for i in range(1,7)};dlcw={i:Counter() for i in range(1,7)}
        drks=Counter();drkw=Counter();dps=Counter();dpw=Counter();dvc=defaultdict(Counter)
        for rid in days[day]:
            classes={lane:by[rid][lane][1] for lane in range(1,7)}
            lcp=b.lc_probs(classes,gp,lcs,lcw)
            rfraw=[max(lcp[l-1]*(by[rid][l][2]/b.NEUTRAL),b.EPS) for l in range(1,7)]
            s=sum(rfraw);rfp=[x/s for x in rfraw]
            exraw=[]
            for l in range(1,7):
                cls=by[rid][l][1];rk=by[rid][l][4];q,_,_=b.adjusted((l,cls,rk),lcp[l-1],rks,rkw)
                exraw.append(max(rfp[l-1]*(q/max(lcp[l-1],b.EPS)),b.EPS))
            s=sum(exraw);exp=[x/s for x in exraw]
            rcraw=[]
            for l in range(1,7):
                racer=by[rid][l][0];q,_,_=b.rc_adjusted(racer,l,cpri[l],rcs,rct)
                rcraw.append(max(exp[l-1]*(q/max(cpri[l],b.EPS)),b.EPS))
            s=sum(rcraw);rcp=[x/s for x in rcraw]
            opp_lc,_,_=b.opponent_probs(classes,lcp,ps,pw)
            oraw=[max(rcp[i]*(opp_lc[i]/max(lcp[i],b.EPS)),b.EPS) for i in range(6)]
            s=sum(oraw);opp=[x/s for x in oraw]
            vp,vweights=vr.venue_shrunk(vb[rid],gp,vc,vn)
            vraw=[max(opp[i]*(vp[i]/max(gp[i],b.EPS)),b.EPS) for i in range(6)]
            s=sum(vraw);bp=[x/s for x in vraw];tot["vws"]+=sum(vweights);tot["vwn"]+=len(vweights)

            v=vb[rid];prior=vpri.get(v,0.5);raw=[]
            for l in range(1,7):
                racer=by[rid][l][0];q,n,wt=rv_adjusted(racer,v,prior,rvs,rvt)
                raw.append(max(bp[l-1]*(q/max(prior,b.EPS)),b.EPS))
                tot["rvobs"]+=1;tot["rvnoprior"]+=int(n==0);tot["rvws"]+=wt
            s=sum(raw);cp=[x/s for x in raw];winner=wb[rid]

            bll,bbr,bh=b.score(bp,winner);cll,cbr,ch=b.score(cp,winner)
            tot["n"]+=1;tot["bll"]+=bll;tot["bbr"]+=bbr;tot["bh"]+=bh
            tot["cll"]+=cll;tot["cbr"]+=cbr;tot["ch"]+=ch
            z=pv[v];z["n"]+=1;z["bll"]+=bll;z["bbr"]+=bbr;z["cll"]+=cll;z["cbr"]+=cbr

            dlw[winner]+=1;dvc[v][winner]+=1
            for l in range(1,7):
                cls=by[rid][l][1];rk=by[rid][l][4];dlcs[l][cls]+=1;drks[(l,cls,rk)]+=1
            wcls=by[rid][winner][1];wrk=by[rid][winner][4];dlcw[winner][wcls]+=1;drkw[(winner,wcls,wrk)]+=1
            for l in range(1,7):
                for opp_l in range(1,7):
                    if opp_l==l:continue
                    key=(l,classes[l],opp_l,classes[opp_l]);dps[key]+=1
                    if l==winner:dpw[key]+=1

        lw.update(dlw);gn+=sum(dlw.values())
        for l in range(1,7):lcs[l].update(dlcs[l]);lcw[l].update(dlcw[l])
        rks.update(drks);rkw.update(drkw);ps.update(dps);pw.update(dpw)
        for v,cnt in dvc.items():vc[v].update(cnt);vn[v]+=sum(cnt.values())
        for racer,c,f,v in hday.get(day,[]):
            cs[c]+=1;rcs[c][racer]+=1;vs[v]+=1;rvs[v][racer]+=1
            if f<=3:ct[c]+=1;rct[c][racer]+=1;vt[v]+=1;rvt[v][racer]+=1

    n=tot["n"]
    bll=tot["bll"]/n;bbr=tot["bbr"]/n;cll=tot["cll"]/n;cbr=tot["cbr"]/n
    vll=vbr=0;vdll={};vdbr={}
    for v,z in sorted(pv.items()):
        vn0=z["n"];dll=z["cll"]/vn0-z["bll"]/vn0;dbr=z["cbr"]/vn0-z["bbr"]/vn0
        vdll[v]=dll;vdbr[v]=dbr;vll+=dll<0;vbr+=dbr<0
    out={"contract":"V5_CURRENT_CORE_PLUS_RACER_VENUE_INTERACTION_V1","period":{"start":START,"end":END},
      "candidate":{"baseline":["lane","class","recent_form","exhibition_rank","racer_course","opponent_composition","venue_lane"],
                   "added":["racer_x_venue_prior_top3_residual"],"strictly_prior_calendar_day":True,
                   "same_day_results_used":False,"parameter_search":False,"v4_logic":False},
      "coverage":{"completed_races":len(races),"scored":n,"coverage_pct":100*n/len(races),"skipped":skip,
                  "invalid_entry_rows":invalid,"invalid_history_rows":badh,
                  "racer_venue_no_prior_pct":100*tot["rvnoprior"]/tot["rvobs"] if tot["rvobs"] else None,
                  "racer_venue_mean_shrink_weight":tot["rvws"]/tot["rvobs"] if tot["rvobs"] else None,"venue_count":len(pv)},
      "metrics":{"baseline_logloss":bll,"candidate_logloss":cll,"delta_logloss":cll-bll,
                 "baseline_brier":bbr,"candidate_brier":cbr,"delta_brier":cbr-bbr,
                 "baseline_top1":tot["bh"]/n,"candidate_top1":tot["ch"]/n,
                 "venues_better_logloss":vll,"venues_better_brier":vbr},
      "venue_delta_logloss":vdll,"venue_delta_brier":vdbr,
      "safety":{"db_write":False,"production_model_change":False,"line_change":False,"purchase_change":False,"stake_change":False}}
    print("V5_RACER_VENUE_INTERACTION_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
