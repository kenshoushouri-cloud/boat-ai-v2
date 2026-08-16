# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Dict, List, Optional

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-17 phase7-entry-features-v1"

START_DATE = os.getenv("P7_START_DATE", "2025-07-01")
END_DATE = os.getenv("P7_END_DATE", "2026-08-15")

TRAIN_END = "2026-03-01"
VALID_END = "2026-05-01"
OOS1_START = "2026-07-01"
OOS2_START = "2026-08-01"

RULE = {"pr": (11, 20), "mr": (2, 5), "odds": (3.0, 6.0), "race_nos": {7, 8, 9, 10}}
LABEL_PRIORITY = ["historical","final_ab","final","manual","beforeinfo","pre","day","night","morning"]

FEATURE_DIRECTIONS = {
    "head_nat_win": "high",
    "head_local_gap": "high",
    "head_local2_gap": "high",
    "head_local3_gap": "high",
    "head_avg_st": "low",
    "head_motor2": "high",
    "head_motor3": "high",
    "nat_win_vs_field": "high",
    "local_win_vs_field": "high",
    "st_edge_vs_field": "high",
    "motor2_vs_field": "high",
    "motor3_vs_field": "high",
}

def sf(v: Any, d=None):
    try:
        if v is None or v == "":
            return d
        return float(v)
    except Exception:
        return d

def si(v: Any, d=0):
    try:
        if v is None or v == "":
            return d
        return int(float(v))
    except Exception:
        return d

def next_day(s: str) -> str:
    return (datetime.strptime(s, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

def month_starts(a: str, b: str):
    cur = datetime.strptime(a[:7] + "-01", "%Y-%m-%d")
    end = datetime.strptime(b[:7] + "-01", "%Y-%m-%d")
    while cur <= end:
        yield cur.strftime("%Y-%m-01")
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

def month_end(s: str) -> str:
    d = datetime.strptime(s, "%Y-%m-%d")
    if d.month == 12:
        d = d.replace(year=d.year + 1, month=1)
    else:
        d = d.replace(month=d.month + 1)
    return d.strftime("%Y-%m-%d")

def period_name(ds: str) -> str:
    if ds < TRAIN_END:
        return "TRAIN"
    if ds < VALID_END:
        return "VALID"
    if ds < OOS1_START:
        return "TEST"
    if ds < OOS2_START:
        return "OOS1"
    return "OOS2"

def qtile(vals: List[float], q: float) -> Optional[float]:
    xs = sorted(v for v in vals if v is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac

def metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    hits = sum(int(r["hit"]) for r in rows)
    ret = sum(int(r["ret"]) for r in rows)
    inv = n * 100
    longest = cur = 0
    bankroll = peak = maxdd = 0
    for r in sorted(rows, key=lambda x: (x["date"], x["race_id"])):
        if r["hit"]:
            cur = 0
        else:
            cur += 1
            longest = max(longest, cur)
        bankroll += int(r["ret"]) - 100
        peak = max(peak, bankroll)
        maxdd = max(maxdd, peak - bankroll)
    return {
        "n": n, "hits": hits,
        "hit_rate": hits / n * 100 if n else 0.0,
        "roi": ret / inv * 100 if inv else 0.0,
        "profit": ret - inv,
        "lose_streak": longest,
        "maxdd": maxdd,
    }

def fmt(m: Dict[str, Any]) -> str:
    return (f"n={m['n']} hits={m['hits']} hit={m['hit_rate']:.1f}% "
            f"ROI={m['roi']:.1f}% profit={m['profit']} "
            f"LS={m['lose_streak']} DD={m['maxdd']}")

def label_priority(label: str) -> int:
    s = str(label or "").strip().lower()
    try:
        return LABEL_PRIORITY.index(s)
    except ValueError:
        return len(LABEL_PRIORITY) + 100

def choose_weather_label(exh_labels, weather_labels, cond_labels):
    common = []
    for label, lanes in exh_labels.items():
        if len(lanes) == 6 and label in weather_labels and len(cond_labels.get(label, {})) == 6:
            common.append(label)
    if not common:
        return None
    return sorted(common, key=lambda x: (label_priority(x), str(x)))[0]

def fetch_month(ms: str, mx: str):
    a = max(START_DATE, ms)
    b = min(next_day(END_DATE), mx)
    if a >= b:
        return [], [], [], [], [], [], []
    ra, rb = a.replace("-", ""), b.replace("-", "")
    races = fetch_all("select * from v2_races where race_date >= %s and race_date < %s order by race_date,venue_id,race_no",(a,b))
    entries = fetch_all("select * from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane",(ra,rb))
    odds = fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s order by race_id,ticket",(ra,rb))
    results = fetch_all("select race_id,trifecta_ticket,coalesce(trifecta_payout_yen,trifecta_payout) payout from v2_results where race_id >= %s and race_id < %s",(ra,rb))
    exh = fetch_all("select race_id,snapshot_label,lane,exhibition_time from v2_realtime_exhibition_snapshots where race_id >= %s and race_id < %s order by race_id,snapshot_label,lane",(ra,rb))
    weather = fetch_all("select race_id,snapshot_label,wind_speed_m,weather,wave_height_cm from v2_realtime_weather_snapshots where race_id >= %s and race_id < %s order by race_id,snapshot_label,snapshot_at",(ra,rb))
    cond = fetch_all("select race_id,snapshot_label,lane from v2_realtime_racer_condition_snapshots where race_id >= %s and race_id < %s order by race_id,snapshot_label,lane",(ra,rb))
    return races, entries, odds, results, exh, weather, cond

def valid_rate(v: Any, lo: float, hi: float) -> Optional[float]:
    x = sf(v, None)
    if x is None or not (lo <= x <= hi):
        return None
    return x

def feature_row(entries: List[Dict[str, Any]], head: int) -> Dict[str, Optional[float]]:
    by = v24._entry_by_lane(entries)
    h = by.get(head)
    if not h:
        return {}
    others = [by[i] for i in range(1,7) if i != head and i in by]
    if len(others) != 5:
        return {}

    def val(e, key, lo, hi):
        return valid_rate(e.get(key), lo, hi)

    def avg_other(key, lo, hi):
        vals = [val(e,key,lo,hi) for e in others]
        vals = [x for x in vals if x is not None]
        return mean(vals) if len(vals) >= 4 else None

    nat = val(h,"national_win_rate",0.01,10.0)
    local = val(h,"local_win_rate",0.01,10.0)
    n2 = val(h,"national_place2_rate",0.01,100.0)
    n3 = val(h,"national_place3_rate",0.01,100.0)
    l2 = val(h,"local_place2_rate",0.01,100.0)
    l3 = val(h,"local_place3_rate",0.01,100.0)
    st = val(h,"avg_st",0.01,0.60)
    m2 = val(h,"motor_place2_rate",0.01,100.0)
    m3 = val(h,"motor_place3_rate",0.01,100.0)

    onat = avg_other("national_win_rate",0.01,10.0)
    olocal = avg_other("local_win_rate",0.01,10.0)
    ost = avg_other("avg_st",0.01,0.60)
    om2 = avg_other("motor_place2_rate",0.01,100.0)
    om3 = avg_other("motor_place3_rate",0.01,100.0)

    return {
        "head_nat_win": nat,
        "head_local_gap": (local-nat) if local is not None and nat is not None else None,
        "head_local2_gap": (l2-n2) if l2 is not None and n2 is not None else None,
        "head_local3_gap": (l3-n3) if l3 is not None and n3 is not None else None,
        "head_avg_st": st,
        "head_motor2": m2,
        "head_motor3": m3,
        "nat_win_vs_field": (nat-onat) if nat is not None and onat is not None else None,
        "local_win_vs_field": (local-olocal) if local is not None and olocal is not None else None,
        "st_edge_vs_field": (ost-st) if st is not None and ost is not None else None,
        "motor2_vs_field": (m2-om2) if m2 is not None and om2 is not None else None,
        "motor3_vs_field": (m3-om3) if m3 is not None and om3 is not None else None,
    }

def match_n02(row: Dict[str, Any]) -> bool:
    return (RULE["pr"][0] <= si(row.get("prob_rank"),999) <= RULE["pr"][1]
            and RULE["mr"][0] <= si(row.get("market_rank"),999) <= RULE["mr"][1]
            and RULE["odds"][0] <= (sf(row.get("odds"),0) or 0) < RULE["odds"][1])

def select_ev(rows):
    if not rows:
        return None
    return max(rows,key=lambda r: (sf(r.get("raw_ev"),0) or 0, sf(r.get("prob"),0) or 0))

def apply_segment(rows, feature: str, threshold: float, direction: str):
    out = []
    for r in rows:
        v = r["features"].get(feature)
        if v is None:
            continue
        if direction == "high" and v >= threshold:
            out.append(r)
        elif direction == "low" and v <= threshold:
            out.append(r)
    return out

def print_periods(label: str, rows: List[Dict[str, Any]]):
    print(f"\n{label}", flush=True)
    for p in ("TRAIN","VALID","TEST","OOS1","OOS2"):
        rr = [r for r in rows if period_name(r["date"]) == p]
        print(f"  {p}: {fmt(metrics(rr))}", flush=True)

def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL ãå¿è¦ã§ã")

    print(f"â analyze_n02_phase7_features_pg.py VERSION {VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("èª­ã¿åãå°ç¨ãN02/WIND_LT4ã¯å¤æ´ãã¾ããã", flush=True)
    print("thresholdã¯TRAINæéã ãããåºå®ããOOSã¯é¾å¤æ±ºå®ã«ä½¿ãã¾ããã", flush=True)
    print("NOTE: ç¾è¡v24 _lane_raw_strength() ã¯motor/boatãåºå®å¤ã§æ±ããããå®ã¢ã¼ã¿ã¼æç¸¾ã¯probè¨ç®ã«ç´æ¥å¥ã£ã¦ãã¾ããã", flush=True)

    rows_all = []

    for ms in month_starts(START_DATE, END_DATE):
        races, entries, odds, results, exh, weather, cond = fetch_month(ms, month_end(ms))
        eb = defaultdict(list)
        for x in entries:
            eb[str(x.get("race_id") or "")].append(x)

        ob = defaultdict(dict)
        for x in odds:
            rid = str(x.get("race_id") or "")
            t = v24._norm_ticket(x.get("ticket"))
            o = sf(x.get("odds"),0)
            if rid and t and o and o > 0:
                ob[rid][t] = o

        rb = {}
        for x in results:
            rid = str(x.get("race_id") or "")
            t = v24._norm_ticket(x.get("trifecta_ticket"))
            p = si(x.get("payout"),0)
            if rid and t and p > 0:
                rb[rid] = (t,p)

        xb = defaultdict(lambda: defaultdict(set))
        for x in exh:
            rid = str(x.get("race_id") or "")
            lab = str(x.get("snapshot_label") or "")
            lane = si(x.get("lane"),0)
            if rid and lab and 1 <= lane <= 6 and x.get("exhibition_time") is not None:
                xb[rid][lab].add(lane)

        wb = defaultdict(dict)
        for x in weather:
            rid = str(x.get("race_id") or "")
            lab = str(x.get("snapshot_label") or "")
            if rid and lab:
                wb[rid][lab] = x

        cb = defaultdict(lambda: defaultdict(dict))
        for x in cond:
            rid = str(x.get("race_id") or "")
            lab = str(x.get("snapshot_label") or "")
            lane = si(x.get("lane"),0)
            if rid and lab and 1 <= lane <= 6:
                cb[rid][lab][lane] = x

        month_ready = month_n02 = 0

        for race in races:
            rid = str(race.get("race_id") or "")
            ent = eb.get(rid,[])
            odd = ob.get(rid,{})
            res = rb.get(rid)
            if len(v24._entry_by_lane(ent)) != 6 or not res:
                continue
            ok,_ = v24._validate_odds_snapshot(odd)
            if not ok:
                continue

            lab = choose_weather_label(xb.get(rid,{}), wb.get(rid,{}), cb.get(rid,{}))
            if not lab:
                continue
            month_ready += 1

            rno = si(race.get("race_no"),0)
            if rno not in RULE["race_nos"]:
                continue

            venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            ranked = v24._rank_candidates(ent,venue,odd)
            sel = select_ev([x for x in ranked if match_n02(x)])
            if not sel:
                continue

            ticket = str(sel.get("ticket") or "")
            head = si(ticket.split("-")[0],0)
            feats = feature_row(ent,head)
            if not feats:
                continue

            rt,payout = res
            hit = ticket == rt
            wind = sf(wb[rid][lab].get("wind_speed_m"),None)

            rows_all.append({
                "race_id":rid,
                "date":str(race.get("race_date") or "")[:10],
                "venue":venue,
                "race_no":rno,
                "ticket":ticket,
                "head":head,
                "wind":wind,
                "hit":hit,
                "ret":payout if hit else 0,
                "features":feats,
            })
            month_n02 += 1

        print(f"month={ms[:7]} races={len(races)} ready={month_ready} n02={month_n02}", flush=True)

    wind_lt4 = [r for r in rows_all if r["wind"] is not None and r["wind"] < 4.0]
    wind_ge4 = [r for r in rows_all if r["wind"] is not None and r["wind"] >= 4.0]

    print("\n"+"="*96, flush=True)
    print("=== BASELINE ===", flush=True)
    print_periods("N02_BASE", rows_all)
    print_periods("N02_WIND_LT4", wind_lt4)
    print_periods("WIND_GE4_RESERVE", wind_ge4)

    print("\n"+"="*96, flush=True)
    print("=== FEATURE QUALITY / HIT-vs-MISS (descriptive only) ===", flush=True)
    for f in FEATURE_DIRECTIONS:
        hit_vals = [r["features"].get(f) for r in wind_lt4 if r["hit"] and r["features"].get(f) is not None]
        miss_vals = [r["features"].get(f) for r in wind_lt4 if (not r["hit"]) and r["features"].get(f) is not None]
        all_vals = hit_vals + miss_vals
        hm = mean(hit_vals) if hit_vals else None
        mm = mean(miss_vals) if miss_vals else None
        hs = f"{hm:.3f}" if hm is not None else "NA"
        ms2 = f"{mm:.3f}" if mm is not None else "NA"
        print(f"{f}: coverage={len(all_vals)}/{len(wind_lt4)} hit_mean={hs} miss_mean={ms2}", flush=True)

    print("\n"+"="*96, flush=True)
    print("=== TRAIN-LOCKED SINGLE-FEATURE SEGMENTS on N02_WIND_LT4 ===", flush=True)

    train_w = [r for r in wind_lt4 if period_name(r["date"]) == "TRAIN"]
    shortlist = []

    for f,direction in FEATURE_DIRECTIONS.items():
        train_vals = [r["features"].get(f) for r in train_w if r["features"].get(f) is not None]
        if len(train_vals) < 20:
            print(f"{f}: SKIP train_coverage={len(train_vals)}", flush=True)
            continue

        threshold = qtile(train_vals, 0.67 if direction == "high" else 0.33)
        if threshold is None:
            continue

        seg = apply_segment(wind_lt4,f,threshold,direction)
        print(f"\n{f} direction={direction} TRAIN_LOCKED_THRESHOLD={threshold:.4f}", flush=True)

        pmets = {}
        for p in ("TRAIN","VALID","TEST","OOS1","OOS2"):
            rr = [r for r in seg if period_name(r["date"]) == p]
            m = metrics(rr)
            pmets[p] = m
            print(f"  {p}: {fmt(m)}", flush=True)

        pre = [r for r in seg if r["date"] < OOS1_START]
        pre_m = metrics(pre)

        discovery_pass = (
            pmets["TRAIN"]["n"] >= 15 and
            pmets["VALID"]["n"] >= 5 and
            pmets["TEST"]["n"] >= 5 and
            pmets["TRAIN"]["roi"] >= 100 and
            pmets["VALID"]["roi"] >= 100 and
            pmets["TEST"]["roi"] >= 100 and
            pre_m["roi"] >= 120
        )

        print(f"  PRE_OOS={fmt(pre_m)} DISCOVERY={'PASS' if discovery_pass else 'WAIT'}", flush=True)
        print(f"  OOS_CHECK_ONLY: OOS1_ROI={pmets['OOS1']['roi']:.1f}% OOS2_ROI={pmets['OOS2']['roi']:.1f}%", flush=True)

        if discovery_pass:
            shortlist.append((f,threshold,direction,pre_m,pmets["OOS1"],pmets["OOS2"]))

    print("\n"+"="*96, flush=True)
    print("=== RESCUE ANALYSIS: WIND>=4, same TRAIN-locked thresholds ===", flush=True)
    for f,threshold,direction,_,_,_ in shortlist:
        seg = apply_segment(wind_ge4,f,threshold,direction)
        print(f"\nRESCUE {f} threshold={threshold:.4f} direction={direction}", flush=True)
        for p in ("TRAIN","VALID","TEST","OOS1","OOS2"):
            rr = [r for r in seg if period_name(r["date"]) == p]
            print(f"  {p}: {fmt(metrics(rr))}", flush=True)

    print("\n"+"="*96, flush=True)
    print("=== PHASE7 SHORTLIST (PRE-OOS selection only) ===", flush=True)
    if not shortlist:
        print("PRE-OOS PASSãªããè¿½å ãã£ã«ã¿ã¼ã¯æ¡ç¨ããªãã", flush=True)
    else:
        for i,(f,th,direction,pre_m,o1,o2) in enumerate(sorted(shortlist,key=lambda x:(x[3]["roi"],x[3]["n"]),reverse=True),1):
            print(
                f"{i:02d}. {f} {direction} threshold={th:.4f} "
                f"PRE_OOS {fmt(pre_m)} | OOS1 n={o1['n']} ROI={o1['roi']:.1f}% "
                f"OOS2 n={o2['n']} ROI={o2['roi']:.1f}%",
                flush=True
            )

    print("\nIMPORTANT:", flush=True)
    print("- ãã®çµæã ãã§æ¬çªæ¡ä»¶ã¯å¤æ´ãã¾ããã", flush=True)
    print("- OOS1/OOS2ãè¦ã¦thresholdãåããã¾ããã", flush=True)
    print("- æ¬¡æ®µéã§shortlistã®é å¥æ§ã¨è³¼å¥é »åº¦ã¸ã®å¯ä¸ãæ¯è¼ãã¾ãã", flush=True)
    print("=== phase7 finished ===", flush=True)

if __name__ == "__main__":
    main()