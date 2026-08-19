# -*- coding: utf-8 -*-
from __future__ import annotations

import math, os
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-19 v24-motor-rank-impact-v1"
START_DATE = os.getenv("MOTOR_AUDIT_START_DATE", "2025-07-01")
END_DATE = os.getenv("MOTOR_AUDIT_END_DATE", "2026-08-15")
TRAIN_END = "2026-03-01"
VALID_END = "2026-05-01"
OOS1_START = "2026-07-01"
OOS2_START = "2026-08-01"
PROGRESS_EVERY = max(1, int(os.getenv("MOTOR_AUDIT_PROGRESS_EVERY", "5000")))


def sf(v, d=None):
    try: return float(v) if v not in (None, "") else d
    except Exception: return d


def si(v, d=0):
    try: return int(float(v)) if v not in (None, "") else d
    except Exception: return d


def period(ds):
    if ds < TRAIN_END: return "TRAIN"
    if ds < VALID_END: return "VALID"
    if ds < OOS1_START: return "TEST"
    if ds < OOS2_START: return "OOS1"
    return "OOS2"


def next_day(s):
    return (datetime.strptime(s, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def months(a, b):
    d = datetime.strptime(a[:7] + "-01", "%Y-%m-%d")
    e = datetime.strptime(b[:7] + "-01", "%Y-%m-%d")
    while d <= e:
        yield d.strftime("%Y-%m-01")
        d = d.replace(year=d.year+1, month=1) if d.month == 12 else d.replace(month=d.month+1)


def mend(s):
    d = datetime.strptime(s, "%Y-%m-%d")
    d = d.replace(year=d.year+1, month=1) if d.month == 12 else d.replace(month=d.month+1)
    return d.strftime("%Y-%m-%d")


def valid_motor2(v):
    x = sf(v, None)
    return x if x is not None and 0.0 <= x <= 100.0 else 33.0


def raw_strength(entry: Dict[str, Any], lane: int, venue: str, motor2_real: bool) -> float:
    cls = si(entry.get("racer_class"), 2)
    cls_w = v24.CLASS_WEIGHT.get(cls, 0.55)
    win_rate = sf(entry.get("national_win_rate"), 0.0) or 0.0
    nat2 = sf(entry.get("national_place2_rate"), 32.0)
    loc2 = sf(entry.get("local_place2_rate"), 30.0)
    avg_st = sf(entry.get("avg_st"), 0.18)
    nat2 = 32.0 if nat2 is None else nat2
    loc2 = 30.0 if loc2 is None else loc2
    avg_st = 0.18 if avg_st is None else avg_st
    mot2 = valid_motor2(entry.get("motor_place2_rate")) if motor2_real else 33.0
    boat2 = 34.0
    course_bias = v24.VENUE_COURSE_BIAS.get(venue, v24.DEFAULT_COURSE_BIAS).get(lane, v24.DEFAULT_COURSE_BIAS[lane])
    st_score = max(0.0, min(1.0, (0.24 - avg_st) / 0.12))
    return (cls_w*1.00 + win_rate*0.16 + (nat2/100)*0.90 + (loc2/100)*0.55 +
            (mot2/100)*0.45 + (boat2/100)*0.25 + st_score*0.35 + course_bias*0.22)


def probs(entries: List[Dict[str, Any]], venue: str, motor2_real: bool):
    by = v24._entry_by_lane(entries)
    raw = {i: raw_strength(by[i], i, venue, motor2_real) for i in range(1,7)}
    w = {i: math.exp(raw[i]/v24.PROB_TEMP) for i in range(1,7)}
    total = sum(w.values())
    out = {}
    for a in range(1,7):
        pa = w[a]/total; tb = total-w[a]
        for b in range(1,7):
            if b == a: continue
            pb = w[b]/tb; tc = tb-w[b]
            for c in range(1,7):
                if c in (a,b): continue
                out[f"{a}-{b}-{c}"] = pa*pb*(w[c]/tc)
    return out


def ranks(p):
    return {t:i for i,(t,_) in enumerate(sorted(p.items(), key=lambda kv:(-kv[1], kv[0])), 1)}


def stat_new():
    return dict(n=0, rank_sum=0, prob_sum=0.0, top1=0, top3=0, top5=0, top10=0, top20=0, b45=0, b1120=0)


def stat_add(s, r, p):
    s["n"] += 1; s["rank_sum"] += r; s["prob_sum"] += p
    s["top1"] += r <= 1; s["top3"] += r <= 3; s["top5"] += r <= 5
    s["top10"] += r <= 10; s["top20"] += r <= 20
    s["b45"] += 4 <= r <= 5; s["b1120"] += 11 <= r <= 20


def pc(x,n): return x/n*100 if n else 0.0


def fmt(label,s):
    n=s["n"]; ar=s["rank_sum"]/n if n else 0; ap=s["prob_sum"]/n*100 if n else 0
    return (f"{label}: n={n} avg_winner_rank={ar:.3f} avg_winner_prob={ap:.4f}% "
            f"top1={pc(s['top1'],n):.3f}% top3={pc(s['top3'],n):.3f}% top5={pc(s['top5'],n):.3f}% "
            f"top10={pc(s['top10'],n):.3f}% top20={pc(s['top20'],n):.3f}% "
            f"rank4_5={pc(s['b45'],n):.3f}% rank11_20={pc(s['b1120'],n):.3f}%")


def fetch_month(ms,mx):
    a=max(START_DATE,ms); b=min(next_day(END_DATE),mx)
    if a>=b: return [],[],[]
    ra=a.replace('-',''); rb=b.replace('-','')
    races=fetch_all("select race_id,race_date,venue_id,venue_code,race_no from v2_races where race_date >= %s and race_date < %s order by race_date,venue_id,race_no",(a,b))
    entries=fetch_all("select race_id,lane,racer_class,national_win_rate,national_place2_rate,local_place2_rate,avg_st,motor_place2_rate from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane",(ra,rb))
    results=fetch_all("select race_id,trifecta_ticket,official,result_status,race_status from v2_results where race_date >= %s and race_date < %s and trifecta_ticket is not null order by race_id",(a,b))
    return races,entries,results


def main():
    if not os.getenv("DATABASE_URL"): raise RuntimeError("DATABASE_URL ãå¿è¦ã§ãã")
    print(f"â analyze_v24_motor_rank_impact_pg.py VERSION {VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("èª­ã¿åãå°ç¨ãDBæ´æ°ã»LINEéç¥ã»æ¬çªå¤å®ã»N02æ¡ä»¶å¤æ´ãªãã", flush=True)
    print("éå»ã®å®å¨ãªåæç¹ãªããºå±¥æ­´ãä¸è¶³ãã¦ãããã market_rank/ROI ã¯è©ä¾¡ãããç¢ºå®çµæã«å¯¾ããprob_rankå¤åãè¨ºæ­ãã¾ãã", flush=True)

    allstats={"BASE":stat_new(),"MOTOR2":stat_new()}
    pst={p:{"BASE":stat_new(),"MOTOR2":stat_new()} for p in ("TRAIN","VALID","TEST","OOS1","OOS2")}
    mst=defaultdict(lambda:{"BASE":stat_new(),"MOTOR2":stat_new()})
    trans=Counter(); improved=worsened=same=delta_sum=processed=skip_ent=bad_result=0

    for ms in months(START_DATE,END_DATE):
        races,entries,results=fetch_month(ms,mend(ms))
        eb=defaultdict(list)
        for x in entries: eb[str(x.get("race_id") or "")].append(x)
        rb={}
        for x in results:
            if x.get("official") is False: bad_result+=1; continue
            rs=str(x.get("result_status") or ""); rcs=str(x.get("race_status") or "")
            if (rs and rs!="official") or (rcs and rcs!="official"): bad_result+=1; continue
            rid=str(x.get("race_id") or ""); t=v24._norm_ticket(x.get("trifecta_ticket"))
            if rid and t: rb[rid]=t
        mp=0
        for race in races:
            rid=str(race.get("race_id") or ""); win=rb.get(rid)
            if not win: continue
            ent=eb.get(rid,[])
            if len(v24._entry_by_lane(ent))!=6: skip_ent+=1; continue
            venue=str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            ds=str(race.get("race_date") or "")[:10]; per=period(ds); mon=ds[:7]
            pb=probs(ent,venue,False); pm=probs(ent,venue,True)
            rbm=ranks(pb); rmm=ranks(pm)
            br=rbm.get(win); mr=rmm.get(win)
            if br is None or mr is None: continue
            stat_add(allstats["BASE"],br,pb[win]); stat_add(allstats["MOTOR2"],mr,pm[win])
            stat_add(pst[per]["BASE"],br,pb[win]); stat_add(pst[per]["MOTOR2"],mr,pm[win])
            stat_add(mst[mon]["BASE"],br,pb[win]); stat_add(mst[mon]["MOTOR2"],mr,pm[win])
            d=mr-br; delta_sum+=d
            if d<0: improved+=1
            elif d>0: worsened+=1
            else: same+=1
            bl=11<=br<=20; ml=11<=mr<=20; bm=4<=br<=5; mm=4<=mr<=5
            trans['low_kept' if bl and ml else 'low_added' if (not bl and ml) else 'low_removed' if (bl and not ml) else 'low_none'] += 1
            trans['mid_kept' if bm and mm else 'mid_added' if (not bm and mm) else 'mid_removed' if (bm and not mm) else 'mid_none'] += 1
            processed+=1; mp+=1
            if processed%PROGRESS_EVERY==0: print(f"PROGRESS processed={processed} date={ds} race_id={rid}",flush=True)
        print(f"month={ms[:7]} races={len(races)} processed={mp}",flush=True)

    print("\n=== OVERALL WINNER RANK QUALITY ===")
    print(fmt("BASE",allstats["BASE"])); print(fmt("MOTOR2",allstats["MOTOR2"]))
    print("\n=== PERIOD COMPARISON ===")
    for p in ("TRAIN","VALID","TEST","OOS1","OOS2"):
        b=pst[p]["BASE"]; m=pst[p]["MOTOR2"]
        print(f"[{p}]"); print(fmt("BASE",b)); print(fmt("MOTOR2",m))
        if b['n'] and m['n']:
            print(f"  vs BASE: avg_rank_delta={(m['rank_sum']/m['n'])-(b['rank_sum']/b['n']):+.4f} top1_delta={pc(m['top1'],m['n'])-pc(b['top1'],b['n']):+.3f}pt top10_delta={pc(m['top10'],m['n'])-pc(b['top10'],b['n']):+.3f}pt top20_delta={pc(m['top20'],m['n'])-pc(b['top20'],b['n']):+.3f}pt")

    n=improved+worsened+same
    print("\n=== WINNER RANK MOVEMENT BASE -> MOTOR2 ===")
    print(f"evaluated={n} improved={improved} ({pc(improved,n):.2f}%) worsened={worsened} ({pc(worsened,n):.2f}%) same={same} ({pc(same,n):.2f}%) avg_rank_delta={(delta_sum/n if n else 0):+.4f}")
    print("\n=== CURRENT V24 PROB_RANK BAND IMPACT ===")
    print(f"LOW(11-20): kept={trans['low_kept']} added_winner_into_band={trans['low_added']} removed_winner_from_band={trans['low_removed']} none={trans['low_none']}")
    print(f"MID(4-5): kept={trans['mid_kept']} added_winner_into_band={trans['mid_added']} removed_winner_from_band={trans['mid_removed']} none={trans['mid_none']}")
    print("\n=== MONTHLY STABILITY ===")
    for mon in sorted(mst):
        b=mst[mon]['BASE']; m=mst[mon]['MOTOR2']
        if not b['n'] or not m['n']: continue
        print(f"{mon}: n={b['n']} avg_rank_delta={(m['rank_sum']/m['n'])-(b['rank_sum']/b['n']):+.4f} top10_delta={pc(m['top10'],m['n'])-pc(b['top10'],b['n']):+.3f}pt winner_prob_delta={(m['prob_sum']/m['n']-b['prob_sum']/b['n'])*100:+.4f}pt")
    print("\n=== AUDIT ===")
    print(f"processed={processed} skipped_entries={skip_ent} invalid_result_rows={bad_result}")
    print("\n=== INTERPRETATION ===")
    print("OOS1/OOS2ã§ãé ä½ã»TopKãå®å®æ¹åãããªããæ¬¡ã¯MOTOR2ãæ¬çªå¤æ´ããForward Shadowåãããã®æç¹ã®market_rank/odds/çµæ/ROIãä¿å­ãã¾ãã")
    print("RESULT=PASS")

if __name__ == '__main__': main()