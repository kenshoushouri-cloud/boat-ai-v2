# -*- coding: utf-8 -*-
"""
feature_lab_pg.py

Feature Lab v1:
- BASELINE
- PREVIOUS_ST_FIXED
- RACER_COURSE
- PREVIOUS_ST_PLUS_RACER_COURSE

1レース120通りは保存せず、期間・設定ごとの集計4行だけ保存します。
本番判定・LINE通知・購入処理は変更しません。
"""

from __future__ import annotations
import math, os, re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from db_pg import execute, fetch_all, upsert_rows
import v22_realtime_decision_engine_pg as base

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime("%Y-%m-%d")
START_DATE = os.getenv("FEATURE_LAB_START_DATE", TODAY)
END_DATE = os.getenv("FEATURE_LAB_END_DATE", TODAY)
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab")
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab")
SAVE_RESULTS = os.getenv("FEATURE_LAB_SAVE", "1").lower() not in {"0","false","no"}

CONFIGS = {
    "BASELINE": (False, False),
    "PREVIOUS_ST_FIXED": (True, False),
    "RACER_COURSE": (False, True),
    "PREVIOUS_ST_PLUS_RACER_COURSE": (True, True),
}

def sf(v: Any, d: float=0.0) -> float:
    try: return d if v in (None, "") else float(v)
    except Exception: return d

def si(v: Any, d: int=0) -> int:
    try: return d if v in (None, "") else int(float(v))
    except Exception: return d

def ticket(v: Any) -> str:
    n = re.findall(r"[1-6]", str(v or ""))
    return f"{n[0]}-{n[1]}-{n[2]}" if len(n) >= 3 else ""

def result_ticket(r: Dict[str, Any]) -> str:
    for k in ("result_trifecta","trifecta","winning_ticket","result","finish_order"):
        t = ticket(r.get(k))
        if t: return t
    a = si(r.get("first_lane") or r.get("first") or r.get("rank1"))
    b = si(r.get("second_lane") or r.get("second") or r.get("rank2"))
    c = si(r.get("third_lane") or r.get("third") or r.get("rank3"))
    return f"{a}-{b}-{c}" if all(1 <= x <= 6 for x in (a,b,c)) else ""

def ensure_schema() -> None:
    sqls = [
        "create table if not exists v2_feature_lab_results (id bigserial primary key);",
        "alter table v2_feature_lab_results add column if not exists period_start date;",
        "alter table v2_feature_lab_results add column if not exists period_end date;",
        "alter table v2_feature_lab_results add column if not exists snapshot_label text;",
        "alter table v2_feature_lab_results add column if not exists selector_mode text;",
        "alter table v2_feature_lab_results add column if not exists config_name text;",
        "alter table v2_feature_lab_results add column if not exists evaluated_races integer;",
        "alter table v2_feature_lab_results add column if not exists avg_result_prob_rank numeric;",
        "alter table v2_feature_lab_results add column if not exists top3_rate numeric;",
        "alter table v2_feature_lab_results add column if not exists top5_rate numeric;",
        "alter table v2_feature_lab_results add column if not exists top10_rate numeric;",
        "alter table v2_feature_lab_results add column if not exists top20_rate numeric;",
        "alter table v2_feature_lab_results add column if not exists improved_races integer;",
        "alter table v2_feature_lab_results add column if not exists worsened_races integer;",
        "alter table v2_feature_lab_results add column if not exists same_races integer;",
        "alter table v2_feature_lab_results add column if not exists previous_st_coverage_races integer;",
        "alter table v2_feature_lab_results add column if not exists racer_course_full_coverage_races integer;",
        "alter table v2_feature_lab_results add column if not exists baseline_avg_delta numeric;",
        "alter table v2_feature_lab_results add column if not exists baseline_top5_delta numeric;",
        "alter table v2_feature_lab_results add column if not exists baseline_top10_delta numeric;",
        "alter table v2_feature_lab_results add column if not exists score numeric;",
        "alter table v2_feature_lab_results add column if not exists config jsonb;",
        "alter table v2_feature_lab_results add column if not exists updated_at timestamptz;",
        "create unique index if not exists uq_v2_feature_lab_results on v2_feature_lab_results(period_start,period_end,snapshot_label,selector_mode,config_name);",
    ]
    for s in sqls: execute(s)

def group(rows):
    out = {}
    for r in rows: out.setdefault(str(r.get("race_id")), []).append(r)
    return out

def prev_st_adj(c: Optional[Dict[str, Any]]) -> float:
    if not c or c.get("previous_st") is None: return 0.0
    st = sf(c.get("previous_st"), 0.18)
    return 0.08 if st <= 0.08 else -0.18 if st >= 0.18 else 0.0

def course_adj(s: Optional[Dict[str, Any]]) -> float:
    if not s: return 0.0
    e, t, st = sf(s.get("entry_rate"),16.67), sf(s.get("top3_rate"),33.33), sf(s.get("avg_st"),0.18)
    x = max(-1,min(1,(t-33.33)/40))*0.55 + max(-1,min(1,(0.18-st)/0.08))*0.30 + max(-1,min(1,(e-16.67)/20))*0.15
    return x * 0.20

def make_rank(entries, venue, odds, conds, course_stats, use_st, use_course):
    by = base._entry_by_lane(entries)
    raw, st_count, course_count = {}, 0, 0
    for lane in range(1,7):
        e = by[lane]
        score = base._lane_raw_strength(e, lane, venue)
        if use_st:
            c = conds.get(lane)
            if c and c.get("previous_st") is not None: st_count += 1
            score += prev_st_adj(c)
        if use_course:
            key = (si(e.get("racer_number")), lane)
            s = course_stats.get(key)
            if s: course_count += 1
            score += course_adj(s)
        raw[lane] = score
    w = {i: math.exp(raw[i]/base.PROB_TEMP) for i in range(1,7)}
    total = sum(w.values())
    rows = []
    for a in range(1,7):
        pa, tb = w[a]/total, total-w[a]
        for b in range(1,7):
            if b == a: continue
            pb, tc = w[b]/tb, tb-w[b]
            for c in range(1,7):
                if c in (a,b): continue
                t = f"{a}-{b}-{c}"
                if sf(odds.get(t)) <= 0: continue
                rows.append((t, pa*pb*(w[c]/tc)))
    rows.sort(key=lambda x:x[1], reverse=True)
    return {t:i for i,(t,_) in enumerate(rows,1)}, st_count, course_count

def calc(ranks):
    n = len(ranks)
    if not n: return {"n":0,"avg":999.0,"t3":0.0,"t5":0.0,"t10":0.0,"t20":0.0}
    return {
        "n":n, "avg":sum(ranks)/n,
        "t3":sum(x<=3 for x in ranks)/n*100,
        "t5":sum(x<=5 for x in ranks)/n*100,
        "t10":sum(x<=10 for x in ranks)/n*100,
        "t20":sum(x<=20 for x in ranks)/n*100,
    }

def main():
    print("✅ feature_lab_pg.py VERSION 2026-07-16 feature-lab-v1", flush=True)
    if not os.getenv("DATABASE_URL"): raise RuntimeError("DATABASE_URL が必要です。")
    ensure_schema()
    print(f"PERIOD={START_DATE}..{END_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} SELECTOR_MODE={SELECTOR_MODE}", flush=True)
    print("本番判定・LINE通知・購入処理は変更しません。", flush=True)

    races = fetch_all("select * from v2_races where race_date >= %s and race_date <= %s order by race_date,venue_id,race_no;", (START_DATE,END_DATE))
    ids = [str(r.get("race_id")) for r in races]
    if not ids:
        print("対象レースはありません。", flush=True); return

    entries_by = group(fetch_all("select * from v2_race_entries where race_id=any(%s) order by race_id,lane;", (ids,)))
    cond_by_rows = group(fetch_all("select * from v2_realtime_racer_condition_snapshots where race_id=any(%s) and snapshot_label=%s order by race_id,lane;", (ids,SNAPSHOT_LABEL)))
    cond_by = {rid:{si(x.get("lane")):x for x in rows} for rid,rows in cond_by_rows.items()}

    odds_by = {}
    for r in fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id=any(%s);",(ids,)):
        t,o = ticket(r.get("ticket")),sf(r.get("odds"))
        if t and o>0: odds_by.setdefault(str(r.get("race_id")),{})[t]=o

    course_stats = {}
    for r in fetch_all("select distinct on (racer_number,course) racer_number,course,entry_rate,top3_rate,avg_st,snapshot_date from v2_racer_course_stats_snapshots where snapshot_date <= %s order by racer_number,course,snapshot_date desc;",(END_DATE,)):
        course_stats[(si(r.get("racer_number")),si(r.get("course")))] = r

    next_day = (datetime.strptime(END_DATE,"%Y-%m-%d")+timedelta(days=1)).strftime("%Y%m%d")
    results = {}
    for r in fetch_all("select * from v2_results where race_id >= %s and race_id < %s;",(START_DATE.replace("-",""),next_day)):
        t = result_ticket(r)
        if t: results[str(r.get("race_id"))]=t

    ranks = {name:[] for name in CONFIGS}
    improved = {name:0 for name in CONFIGS}; worsened = {name:0 for name in CONFIGS}; same = {name:0 for name in CONFIGS}
    st_cov = course_cov = eligible = 0

    for race in races:
        rid = str(race.get("race_id")); e = entries_by.get(rid,[]); o = odds_by.get(rid,{}); win = results.get(rid)
        if len(base._entry_by_lane(e)) != 6 or len(o) < 100 or not win: continue
        eligible += 1
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        rr = {}
        for name,(use_st,use_course) in CONFIGS.items():
            rm, sc, cc = make_rank(e,venue,o,cond_by.get(rid,{}),course_stats,use_st,use_course)
            rr[name] = rm.get(win,999)
            if name=="PREVIOUS_ST_FIXED" and sc>0: st_cov += 1
            if name=="RACER_COURSE" and cc==6: course_cov += 1
        b = rr["BASELINE"]
        for name in CONFIGS:
            x = rr[name]; ranks[name].append(x)
            improved[name] += x < b; worsened[name] += x > b; same[name] += x == b

    base_m = calc(ranks["BASELINE"])
    now = datetime.now(JST).isoformat()
    save_rows=[]; report=[]
    for name in CONFIGS:
        m=calc(ranks[name])
        ad = 0 if name=="BASELINE" else m["avg"]-base_m["avg"]
        d5 = 0 if name=="BASELINE" else m["t5"]-base_m["t5"]
        d10 = 0 if name=="BASELINE" else m["t10"]-base_m["t10"]
        score = 0 if name=="BASELINE" else (base_m["avg"]-m["avg"]) + d5*0.20 + d10*0.10 + (m["t20"]-base_m["t20"])*0.05
        report.append((score,name,m,ad,d5,d10))
        save_rows.append({
            "period_start":START_DATE,"period_end":END_DATE,"snapshot_label":SNAPSHOT_LABEL,"selector_mode":SELECTOR_MODE,
            "config_name":name,"evaluated_races":m["n"],"avg_result_prob_rank":m["avg"],
            "top3_rate":m["t3"],"top5_rate":m["t5"],"top10_rate":m["t10"],"top20_rate":m["t20"],
            "improved_races":improved[name],"worsened_races":worsened[name],"same_races":same[name],
            "previous_st_coverage_races":st_cov,"racer_course_full_coverage_races":course_cov,
            "baseline_avg_delta":ad,"baseline_top5_delta":d5,"baseline_top10_delta":d10,"score":score,
            "config":{"previous_st_fixed":{"fast_threshold":0.08,"fast_bonus":0.08,"slow_threshold":0.18,"slow_penalty":0.18},"racer_course_weight":0.20},
            "updated_at":now,
        })
    saved = upsert_rows("v2_feature_lab_results",save_rows,["period_start","period_end","snapshot_label","selector_mode","config_name"]) if SAVE_RESULTS else 0

    print(f"eligible_races={eligible} previous_st_coverage_races={st_cov} racer_course_full_coverage_races={course_cov}",flush=True)
    print("=== FEATURE LAB RESULTS ===",flush=True)
    for score,name,m,ad,d5,d10 in sorted(report,reverse=True):
        print(f"{name}: races={m['n']} avg={m['avg']:.3f} top3={m['t3']:.2f}% top5={m['t5']:.2f}% top10={m['t10']:.2f}% top20={m['t20']:.2f}% avg_delta={ad:+.3f} top5_delta={d5:+.2f}pt top10_delta={d10:+.2f}pt improved={improved[name]} worsened={worsened[name]} same={same[name]} score={score:+.3f}",flush=True)
    print(f"saved_summary_rows={saved}",flush=True)
    print("判定目安: 300R以上で平均順位改善・Top5非悪化・Top10非悪化・改善R>悪化Rを満たす設定だけを採用候補にします。",flush=True)
    print("=== feature lab finished ===",flush=True)

if __name__ == "__main__":
    main()