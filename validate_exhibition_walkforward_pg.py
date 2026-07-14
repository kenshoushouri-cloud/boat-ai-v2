# -*- coding: utf-8 -*-
from __future__ import annotations
import itertools, math, os, re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from db_pg import fetch_all

JST=timezone(timedelta(hours=9))
START=os.getenv("ANALYZE_START_DATE","2026-07-05")
END=os.getenv("ANALYZE_END_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
LABEL=os.getenv("SNAPSHOT_LABEL","final_ab")
MIN_DAYS=max(2,int(os.getenv("WF_MIN_TRAIN_DAYS","4")))
TEMP=2.2
CW={1:.15,2:.55,3:1.15,4:1.55}
VCB={"01":{1:2.762,2:2.747,3:3.385,4:4.070,5:3.537,6:2.343},"06":{1:2.932,2:3.401,3:3.571,4:3.195,5:2.694,6:2.403},"12":{1:3.249,2:3.344,3:2.957,4:2.824,5:2.313,6:1.553},"18":{1:3.509,2:3.116,3:2.908,4:2.648,5:1.380,6:1.355},"24":{1:3.561,2:2.880,3:2.659,4:2.267,5:2.049,6:1.314}}
DCB={1:3.2,2:3.1,3:3.1,4:3.0,5:2.4,6:1.8}
CONFIGS=list(itertools.product([0,.05,.10,.15,.20],[0,.03,.06,.10],[0,.05,.10,.15]))
BASE=(0.,0.,0.); FULL=(.20,.10,0.); BAL=(.20,0.,0.)

def sf(v,d=0.):
    try:return float(str(v).replace(",","")) if v not in (None,"") else d
    except:return d
def si(v,d=0):
    try:return int(float(str(v).replace(",",""))) if v not in (None,"") else d
    except:return d
def nt(v):
    s=str(v or ""); a=re.findall(r"(?<!\d)([1-6])(?!\d)",s)
    if len(a)>=3:return f"{a[0]}-{a[1]}-{a[2]}"
    s=re.sub(r"\D","",s)
    return f"{s[0]}-{s[1]}-{s[2]}" if len(s)>=3 and all(c in "123456" for c in s[:3]) else ""
def centered(r): return {1:1.,2:.6,3:.2,4:-.2,5:-.6,6:-1.}.get(r,0.)
def base(e,l,v):
    st=sf(e.get("avg_st"),.18); ss=max(0,min(1,(.24-st)/.12))
    return CW.get(si(e.get("racer_class"),2),.55)+sf(e.get("national_win_rate"))*.16+sf(e.get("national_place2_rate"),32)/100*.9+sf(e.get("local_place2_rate"),30)/100*.55+.33*.45+.34*.25+ss*.35+VCB.get(v,DCB).get(l,DCB[l])*.22
def probs(r,cfg):
    exw,stw,wp=cfg; raw={}
    for l in range(1,7):
        z=base(r["e"][l],l,r["v"])+exw*centered(si(r["x"][l].get("exhibition_time_rank")))+stw*centered(si(r["x"][l].get("start_timing_rank")))
        if l==1 and r["wind"]>=5:z-=wp
        raw[l]=z
    w={l:math.exp(raw[l]/TEMP) for l in raw}; total=sum(w.values()); out={}
    for a in range(1,7):
        pa=w[a]/total; rb=total-w[a]
        for b in range(1,7):
            if b==a:continue
            pb=w[b]/rb; rc=rb-w[b]
            for c in range(1,7):
                if c in (a,b):continue
                out[f"{a}-{b}-{c}"]=pa*pb*w[c]/rc
    return out
def rank(r,cfg):
    q=probs(r,cfg); ranks={t:i for i,(t,_) in enumerate(sorted(q.items(),key=lambda z:z[1],reverse=True),1)}
    return ranks.get(r["result"],999)
def evals(rs,cfg):
    s=Counter()
    for r in rs:
        k=rank(r,cfg)
        if k>=999:continue
        s["n"]+=1;s["sum"]+=k
        for j in (1,3,5,10,20):s[f"t{j}"]+=int(k<=j)
    return s
def key(s):
    n=s["n"]
    return (999,0,0,0) if not n else (s["sum"]/n,-s["t10"]/n,-s["t5"]/n,-s["t20"]/n)
def merge(a,b):a.update(b)
def show(name,s):
    n=s["n"]; print(f"\n{name}\n  races={n} avg_result_prob_rank={(s['sum']/n if n else 0):.3f}")
    for j in (1,3,5,10,20):print(f"  result_in_top{j}={s[f't{j}']} ({(s[f't{j}']/n*100 if n else 0):.2f}%)")

def load():
    er=fetch_all("""select r.race_id,r.race_date,coalesce(r.venue_id,r.venue_code) venue_id,e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,e.local_place2_rate,e.avg_st from v2_races r join v2_race_entries e on e.race_id=r.race_id where r.race_date between %s and %s order by r.race_id,e.lane""",(START,END))
    xr=fetch_all("select race_id,lane,exhibition_time_rank,start_timing_rank from v2_realtime_exhibition_snapshots where race_date between %s and %s and snapshot_label=%s",(START,END,LABEL))
    wr=fetch_all("select race_id,wind_speed_m from v2_realtime_weather_snapshots where race_date between %s and %s and snapshot_label=%s",(START,END,LABEL))
    endx=(datetime.strptime(END,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y%m%d")
    rr=fetch_all("select race_id,first_lane,second_lane,third_lane,trifecta_ticket from v2_results where race_id >= %s and race_id < %s",(START.replace("-",""),endx))
    d={}
    for z in er:
        rid=str(z["race_id"]); q=d.setdefault(rid,{"date":str(z["race_date"]),"v":str(z["venue_id"]).zfill(2),"e":{},"x":{},"wind":0.,"result":""}); q["e"][si(z["lane"])]=z
    for z in xr:
        rid=str(z["race_id"])
        if rid in d:d[rid]["x"][si(z["lane"])]=z
    for z in wr:
        rid=str(z["race_id"])
        if rid in d:d[rid]["wind"]=sf(z.get("wind_speed_m"))
    for z in rr:
        rid=str(z["race_id"])
        if rid not in d:continue
        a,b,c=si(z.get("first_lane")),si(z.get("second_lane")),si(z.get("third_lane"))
        d[rid]["result"]=f"{a}-{b}-{c}" if all(1<=x<=6 for x in (a,b,c)) else nt(z.get("trifecta_ticket"))
    return [q for q in d.values() if len(q["e"])==6 and len(q["x"])==6 and q["result"]]

def main():
    if not os.getenv("DATABASE_URL"):raise RuntimeError("DATABASE_URL ãå¿è¦ã§ãã")
    print("â validate_exhibition_walkforward_pg.py VERSION 2026-07-15")
    print(f"PERIOD={START}..{END} SNAPSHOT_LABEL={LABEL} MIN_TRAIN_DAYS={MIN_DAYS}")
    rs=load(); by=defaultdict(list)
    for r in rs:by[r["date"]].append(r)
    dates=sorted(by); print(f"eligible_races={len(rs)} dates={len(dates)}")
    wf=Counter(); basec=Counter(); fullc=Counter(); balc=Counter(); chosen=Counter()
    for i in range(MIN_DAYS,len(dates)):
        train=[r for d in dates[:i] for r in by[d]]; test=by[dates[i]]
        cfg=min(CONFIGS,key=lambda c:key(evals(train,c))); chosen[str(cfg)]+=1
        a,b,c,d=evals(test,cfg),evals(test,BASE),evals(test,FULL),evals(test,BAL)
        merge(wf,a);merge(basec,b);merge(fullc,c);merge(balc,d)
        print(f"{dates[i]} selected={cfg} test_races={a['n']} base_avg={b['sum']/b['n']:.2f} wf_avg={a['sum']/a['n']:.2f}")
    show("WALK-FORWARD SELECTED",wf);show("SAME TEST DAYS BASELINE",basec);show("SAME TEST DAYS FULL-PERIOD BEST",fullc);show("SAME TEST DAYS BALANCED",balc)
    print("\nSELECTED CONFIG FREQUENCY")
    for k,v in chosen.most_common():print(f"  {k}: {v} days")
    print("=== exhibition walk-forward validation finished ===")
if __name__=="__main__":main()