# -*- coding: utf-8 -*-
"""
backtest_prob_motor_boat_ablation_pg.py

v24確率モデルの motor2 / boat2 だけを固定アブレーションする読み取り専用OOS診断。
BASE=現行固定33/34, MOTOR=実測motorのみ, BOAT=実測boatのみ, BOTH=両方実測。
係数・PROB_TEMPは変更しない。DB書込/LINE/Production変更なし。
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-24 motor-boat-ablation-v1"
START_DATE = os.getenv("ABLATION_START_DATE", "2026-07-01")
END_DATE = os.getenv("ABLATION_END_DATE", "2026-08-15")
MODES = ("BASE", "MOTOR", "BOAT", "BOTH")


def sf(v: Any, d: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else d
    except Exception:
        return d


def si(v: Any, d: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else d
    except Exception:
        return d


def dates(a: str, b: str) -> Iterable[str]:
    d = datetime.strptime(a, "%Y-%m-%d")
    e = datetime.strptime(b, "%Y-%m-%d")
    while d <= e:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


def lane_strength(entry: Dict[str, Any], lane: int, venue_id: str, mode: str) -> float:
    cls = si(entry.get("racer_class"), 2)
    cls_w = v24.CLASS_WEIGHT.get(cls, 0.55)
    win_rate = sf(entry.get("national_win_rate"), 0.0)
    nat2 = sf(entry.get("national_place2_rate"), 32.0)
    loc2 = sf(entry.get("local_place2_rate"), 30.0)
    mot2 = sf(entry.get("motor_place2_rate"), 33.0) if mode in ("MOTOR", "BOTH") else 33.0
    boat2 = sf(entry.get("boat_place2_rate"), 34.0) if mode in ("BOAT", "BOTH") else 34.0
    avg_st = sf(entry.get("avg_st"), 0.18)
    course_bias = v24.VENUE_COURSE_BIAS.get(venue_id, v24.DEFAULT_COURSE_BIAS).get(
        lane, v24.DEFAULT_COURSE_BIAS[lane]
    )
    st_score = max(0.0, min(1.0, (0.24 - avg_st) / 0.12))
    return (
        cls_w * 1.00
        + win_rate * 0.16
        + (nat2 / 100.0) * 0.90
        + (loc2 / 100.0) * 0.55
        + (mot2 / 100.0) * 0.45
        + (boat2 / 100.0) * 0.25
        + st_score * 0.35
        + course_bias * 0.22
    )


def ticket_probs(entries: List[Dict[str, Any]], venue_id: str, mode: str) -> Dict[str, float]:
    by = v24._entry_by_lane(entries)
    raw = {lane: lane_strength(by[lane], lane, venue_id, mode) for lane in range(1, 7)}
    weights = {lane: math.exp(raw[lane] / v24.PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    out: Dict[str, float] = {}
    for a in range(1, 7):
        pa = weights[a] / total
        tb = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / tb
            tc = tb - weights[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = pa * pb * (weights[c] / tc)
    return out


def rank_of(probs: Dict[str, float], ticket: str) -> int:
    ordered = sorted(probs, key=lambda t: probs[t], reverse=True)
    try:
        return ordered.index(ticket) + 1
    except ValueError:
        return 999


def new_stat() -> Dict[str, float]:
    return {"n": 0, "ll": 0.0, "brier": 0.0, "rank": 0.0}


def add_stat(s: Dict[str, float], probs: Dict[str, float], winner: str) -> None:
    wp = max(sf(probs.get(winner)), 1e-15)
    s["n"] += 1
    s["ll"] += -math.log(wp)
    s["rank"] += rank_of(probs, winner)
    b = 0.0
    for t, p in probs.items():
        y = 1.0 if t == winner else 0.0
        b += (p - y) ** 2
    s["brier"] += b


def emit(label: str, s: Dict[str, float]) -> None:
    n = int(s["n"])
    print(
        f"{label}: n={n} logloss={s['ll']/n if n else 0:.8f} "
        f"brier={s['brier']/n if n else 0:.8f} winner_rank={s['rank']/n if n else 0:.4f}",
        flush=True,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL required")
    print(f"✅ backtest_prob_motor_boat_ablation_pg.py VERSION {VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("POLICY=fixed_ablation_no_coefficient_tuning_read_only", flush=True)

    overall = {m: new_stat() for m in MODES}
    monthly = defaultdict(lambda: {m: new_stat() for m in MODES})
    result_races = full6 = complete_both = 0

    for ds in dates(START_DATE, END_DATE):
        p = ds.replace("-", "")
        np = (datetime.strptime(ds, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
        results = fetch_all(
            """select race_id,trifecta_ticket from v2_results
               where race_date=%s and trifecta_ticket is not null
                 and coalesce(result_status,'')='official'
                 and coalesce(race_status,'')='official'
               order by race_id""", (ds,)
        )
        result_races += len(results)
        rb = {str(r["race_id"]): v24._norm_ticket(r.get("trifecta_ticket")) for r in results}
        if not rb:
            continue
        races = fetch_all("select race_id,venue_id,venue_code from v2_races where race_date=%s", (ds,))
        venues = {str(r["race_id"]): str(r.get("venue_id") or r.get("venue_code") or "").zfill(2) for r in races}
        eb: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for e in fetch_all(
            """select race_id,lane,racer_class,national_win_rate,national_place2_rate,
                      local_place2_rate,avg_st,motor_place2_rate,boat_place2_rate
               from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane""",
            (p, np),
        ):
            rid = str(e.get("race_id") or "")
            if rid in rb:
                eb[rid].append(e)

        for rid, winner in rb.items():
            entries = eb.get(rid, [])
            by = v24._entry_by_lane(entries)
            if len(by) != 6 or not winner:
                continue
            full6 += 1
            if not all(by[i].get("motor_place2_rate") is not None and by[i].get("boat_place2_rate") is not None for i in range(1, 7)):
                continue
            complete_both += 1
            venue = venues.get(rid, "")
            for mode in MODES:
                probs = ticket_probs(entries, venue, mode)
                add_stat(overall[mode], probs, winner)
                add_stat(monthly[ds[:7]][mode], probs, winner)

    print(f"COVERAGE=result_races:{result_races} full6:{full6} compared_complete_both:{complete_both}", flush=True)
    print("=== OVERALL ===", flush=True)
    for mode in MODES:
        emit(mode, overall[mode])
    base = overall["BASE"]
    for mode in ("MOTOR", "BOAT", "BOTH"):
        s = overall[mode]
        n = int(s["n"])
        bn = int(base["n"])
        print(
            f"DELTA_{mode}=logloss:{(s['ll']/n)-(base['ll']/bn):+.8f} "
            f"brier:{(s['brier']/n)-(base['brier']/bn):+.8f} "
            f"winner_rank:{(s['rank']/n)-(base['rank']/bn):+.4f}", flush=True,
        )
    print("=== MONTHLY ===", flush=True)
    for month in sorted(monthly):
        for mode in MODES:
            emit(f"{month}|{mode}", monthly[month][mode])
    print("INTERPRETATION=negative_delta_is_better_identify_motor_vs_boat_contribution_before_any_production_change", flush=True)
    print("RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
