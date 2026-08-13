# -*- coding: utf-8 -*-
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

JST=timezone(timedelta(hours=9))
START=os.getenv("BT_START_DATE","2025-07-01")
VALID=os.getenv("BT_VALID_START_DATE","2026-03-01")
TEST=os.getenv("BT_TEST_START_DATE","2026-06-01")
END=os.getenv("BT_END_DATE",datetime.now(JST).strftime("%Y-%m-%d"))
MIN_T=int(os.getenv("BT2_MIN_SEG_TRAIN","20"))
MIN_V=int(os.getenv("BT2_MIN_SEG_VALID","8"))
MIN_X=int(os.getenv("BT2_MIN_SEG_TEST","5"))
TOP=int(os.getenv("BT2_TOP_N","100"))
BASES=[((11,25),(2,5),(3.,6.),"ev"),((11,25),(2,5),(3.,6.),"prob"),
       ((11,20),(2,5),(3.,6.),"ev"),((11,20),(2,5),(3.,6.),"prob")]
VN={"01":"桐生","02":"戸田","03":"江戸川","04":"平和島","05":"多摩川","06":"浜名湖",
"07":"蒲郡","08":"常滑","09":"津","10":"三国","11":"びわこ","12":"住之江","13":"尼崎",
"14":"鳴門","15":"丸亀","16":"児島","17":"宮島","18":"徳山","19":"下関","20":"若松",
"21":"芦屋","22":"福岡","23":"唐津","24":"大村"}

def sf(x,d=0.):
    try:return float(x)
    except:return d
def si(x,d=0):
    try:return int(float(x))
    except:return d
def nd(s):return (datetime.strptime(s,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y-%m-%d")
def months(a,b):
    d=datetime.strptime(a[:7]+"-01","%Y-%m-%d"); e=datetime.strptime(b[:7]+"-01","%Y-%m-%d")
    while d<=e:
        yield d.strftime("%Y-%m-01")
        d=d.replace(year=d.year+1,month=1) if d.month==12 else d.replace(month=d.month+1)
def me(s):
    d=datetime.strptime(s,"%Y-%m-%d")
    d=d.replace(year=d.year+1,month=1) if d.month==12 else d.replace(month=d.month+1)
    return d.strftime("%Y-%m-%d")
def per(d):return "TRAIN" if d<VALID else ("VALID" if d<TEST else "TEST")
def band(n):return "R01-03" if n<=3 else ("R04-06" if n<=6 else ("R07-09" if n<=9 else "R10-12"))
def cat(name):
    n=name or ""; l=n.lower()
    if "オールレディース" in n or "all ladies" in l:return "all_ladies"
    if "ヴィーナス" in n or "venus" in l:return "venus"
    if "ルーキー" in n or "rookie" in l:return "rookie"
    if "マスターズ" in n or "masters" in l:return "masters"
    if "レディース" in n or "女子" in n or "ladies" in l:return "ladies_other"
    if any(x.lower() in l for x in ("SG","G1","GⅠ","G2","GⅡ","G3","GⅢ")):return "G1_like"
    return "category_other"
def st():return {"n":0,"h":0,"r":0,"mx":0}
def add(s,hit,pay):
    s["n"]+=1
    if hit:s["h"]+=1;s["r"]+=pay;s["mx"]=max(s["mx"],pay)
def met(s):
    inv=s["n"]*100
    return {"n":s["n"],"h":s["h"],"hr":s["h"]/s["n"]*100 if s["n"] else 0,
            "roi":s["r"]/inv*100 if inv else 0,"profit":s["r"]-inv,
            "single":s["mx"]/s["r"]*100 if s["r"] else 0}
def fetch(ms,mx):
    a=max(START,ms); b=min(nd(END),mx)
    if a>=b:return [],[],[],[]
    ra,rb=a.replace("-",""),b.replace("-","")
    r=fetch_all("select * from v2_races where race_date >= %s and race_date < %s order by race_date,venue_id,race_no",(a,b))
    e=fetch_all("select * from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane",(ra,rb))
    o=fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s order by race_id,ticket",(ra,rb))
    z=fetch_all("select race_id,trifecta_ticket,trifecta_payout_yen from v2_results where race_id >= %s and race_id < %s",(ra,rb))
    return r,e,o,z
def best(ranked,b):
    pw,mw,ow,mode=b
    a=[r for r in ranked if pw[0]<=si(r.get("prob_rank"),999)<=pw[1] and mw[0]<=si(r.get("market_rank"),999)<=mw[1] and ow[0]<=sf(r.get("odds"))<ow[1]]
    if not a:return None
    key=(lambda r:(sf(r.get("raw_ev")),sf(r.get("prob")))) if mode=="ev" else (lambda r:(sf(r.get("prob")),sf(r.get("raw_ev"))))
    return max(a,key=key)
def bn(i,b):
    p,m,o,x=b;return f"B{i+1}: pr={p[0]}-{p[1]} mr={m[0]}-{m[1]} odds={o[0]:g}-{o[1]:g} select={x}"

def main():
    if not os.getenv("DATABASE_URL"):raise RuntimeError("DATABASE_URL required")
    print("✅ phase2 VERSION 2026-08-13 exclusion-search-v1")
    print(f"PERIOD={START}..{END} VALID={VALID} TEST={TEST}")
    print("READ ONLY: DB更新・LINE通知・本番変更なし")
    A=defaultdict(st); cov=defaultdict(int)
    for ms in months(START,END):
        races,er,orr,rr=fetch(ms,me(ms)); eb=defaultdict(list); ob=defaultdict(dict); rb={}
        for x in er:eb[str(x.get("race_id") or "")].append(x)
        for x in orr:
            rid=str(x.get("race_id") or ""); t=v24._norm_ticket(x.get("ticket")); od=sf(x.get("odds"))
            if rid and t and od>0:ob[rid][t]=od
        for x in rr:
            rid=str(x.get("race_id") or "");t=v24._norm_ticket(x.get("trifecta_ticket"));pay=si(x.get("trifecta_payout_yen"))
            if rid and t and pay>0:rb[rid]=(t,pay)
        ready=0
        for race in races:
            rid=str(race.get("race_id") or ""); entries=eb.get(rid,[]); odds=ob.get(rid,{})
            if len(v24._entry_by_lane(entries))!=6 or rid not in rb:continue
            ok,_=v24._validate_odds_snapshot(odds)
            if not ok:continue
            ready+=1; d=str(race.get("race_date") or "")[:10]; p=per(d)
            venue=str(race.get("venue_id") or race.get("venue_code") or "").zfill(2); rn=si(race.get("race_no"))
            dims=[("venue",f"{venue}:{VN.get(venue,venue)}"),("race_band",band(rn)),("race_no",f"R{rn:02d}"),
                  ("category",cat(str(race.get("race_name") or ""))),("month",d[:7]),
                  ("venue_band",f"{venue}:{VN.get(venue,venue)}/{band(rn)}")]
            ranked=v24._rank_candidates(entries,venue,odds); rt,pay=rb[rid]
            for bi,b in enumerate(BASES):
                sel=best(ranked,b)
                if not sel:continue
                hit=str(sel.get("ticket") or "")==rt;cov[(bi,p)]+=1
                for dim,val in dims:add(A[(bi,dim,val,p)],hit,pay)
        print(f"month={ms[:7]} races={len(races)} ready={ready}")
    print("\n=== base coverage ===")
    for bi,b in enumerate(BASES):
        print(bn(bi,b), " ".join(f"{p}={cov[(bi,p)]}" for p in ("TRAIN","VALID","TEST")))
    for bi,b in enumerate(BASES):
        print("\n"+"="*80+"\n"+bn(bi,b))
        for dim in ("venue","race_band","race_no","category","venue_band"):
            vals=sorted({k[2] for k in A if k[0]==bi and k[1]==dim}); rows=[]
            for val in vals:
                t,v,x=(met(A[(bi,dim,val,p)]) for p in ("TRAIN","VALID","TEST"))
                if t["n"]<MIN_T or v["n"]<MIN_V or x["n"]<MIN_X:continue
                score=max(0,100-x["roi"])*1.5+max(0,100-v["roi"])+max(0,95-t["roi"])*.5+min(x["n"],30)*.25
                rows.append((score,val,t,v,x))
            rows.sort(reverse=True,key=lambda q:q[0])
            print(f"\n--- {dim}: exclusion candidates ---")
            for score,val,t,v,x in rows[:TOP]:
                flag=" << EXCLUDE候補" if v["roi"]<100 and x["roi"]<100 else ""
                print(f"{val:22s} TRAIN n={t['n']:4d} ROI={t['roi']:6.1f}% VALID n={v['n']:3d} ROI={v['roi']:6.1f}% TEST n={x['n']:3d} hits={x['h']:3d} ROI={x['roi']:6.1f}% profit={x['profit']:7.0f} score={score:6.1f}{flag}")
    print("\n=== monthly stability by base ===")
    for bi,b in enumerate(BASES):
        print("\n"+bn(bi,b))
        for val in sorted({k[2] for k in A if k[0]==bi and k[1]=="month"}):
            s=st()
            for p in ("TRAIN","VALID","TEST"):
                q=A[(bi,"month",val,p)];s["n"]+=q["n"];s["h"]+=q["h"];s["r"]+=q["r"];s["mx"]=max(s["mx"],q["mx"])
            m=met(s);print(f"{val} n={m['n']:4d} hits={m['h']:3d} hit_rate={m['hr']:5.1f}% ROI={m['roi']:6.1f}% profit={m['profit']:7.0f}")
    print("\n=== phase2 analysis finished ===")
if __name__=="__main__":main()