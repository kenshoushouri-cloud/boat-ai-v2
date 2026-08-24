# -*- coding: utf-8 -*-
"""
backtest_prob_actual_motor_shadow_pg.py

v24 の確率式を一切チューニングせず、現在ハードコードされている
motor2=33 / boat2=34 を v2_race_entries の実測2連率に差し替えた場合だけを
OOSで比較する読み取り専用Shadow診断。

目的:
- 馬王型の独立確率モデル改善候補を、安全に検証する。
- Production v24の確率式・閾値・通知は変更しない。

DB書き込みなし / LINEなし / Railway設定変更なし。
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-24 actual-motor-prob-shadow-v1"
START_DATE = os.getenv("MOTOR_PROB_START_DATE", "2026-07-01")
END_DATE = os.getenv("MOTOR_PROB_END_DATE", "2026-08-15")


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


def actual_lane_raw_strength(entry: Dict[str, Any], lane: int, venue_id: str) -> float:
    """v24と同じ係数。motor2/boat2だけ実測値を使う。"""
    cls = si(entry.get("racer_class"), 2)
    cls_w = v24.CLASS_WEIGHT.get(cls, 0.55)
    win_rate = sf(entry.get("national_win_rate"), 0.0)
    nat2 = sf(entry.get("national_place2_rate"), 32.0)
    loc2 = sf(entry.get("local_place2_rate"), 30.0)
    mot2 = sf(entry.get("motor_place2_rate"), 33.0)
    boat2 = sf(entry.get("boat_place2_rate"), 34.0)
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


def actual_ticket_probabilities(entries: List[Dict[str, Any]], venue_id: str) -> Dict[str, float]:
    by_lane = v24._entry_by_lane(entries)
    raw = {lane: actual_lane_raw_strength(by_lane[lane], lane, venue_id) for lane in range(1, 7)}
    weights = {lane: math.exp(raw[lane] / v24.PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    probs: Dict[str, float] = {}
    for a in range(1, 7):
        pa = weights[a] / total
        total_b = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / total_b
            total_c = total_b - weights[b]
            for c in range(1, 7):
                if c == a or c == b:
                    continue
                pc = weights[c] / total_c
                probs[f"{a}-{b}-{c}"] = pa * pb * pc
    return probs


def rank_of(probs: Dict[str, float], ticket: str) -> int:
    ordered = sorted(probs, key=lambda t: probs[t], reverse=True)
    try:
        return ordered.index(ticket) + 1
    except ValueError:
        return 999


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")

    print(f"✅ backtest_prob_actual_motor_shadow_pg.py VERSION {VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("CHANGE_UNDER_TEST=only_replace_v24_default_motor2_33_boat2_34_with_actual_entry_rates", flush=True)
    print("POLICY=read_only_no_production_no_line_no_coefficient_tuning", flush=True)

    total_results = full6 = motor6 = boat6 = compare = 0
    base_logloss = actual_logloss = 0.0
    base_brier = actual_brier = 0.0
    actual_ll_better = actual_rank_better = rank_equal = 0
    base_rank_sum = actual_rank_sum = 0
    monthly = defaultdict(lambda: {"n":0,"base_ll":0.0,"actual_ll":0.0,"better":0})

    for ds in dates(START_DATE, END_DATE):
        p = ds.replace("-", "")
        np = (datetime.strptime(ds, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
        results = fetch_all(
            """
            select race_id,trifecta_ticket
            from v2_results
            where race_date=%s
              and trifecta_ticket is not null
              and coalesce(result_status,'')='official'
              and coalesce(race_status,'')='official'
            order by race_id
            """,
            (ds,),
        )
        total_results += len(results)
        result_map = {str(r.get("race_id") or ""): v24._norm_ticket(r.get("trifecta_ticket")) for r in results}
        if not result_map:
            continue

        races = fetch_all(
            "select race_id,venue_id,venue_code from v2_races where race_date=%s order by venue_id,race_no",
            (ds,),
        )
        venue_map = {
            str(r.get("race_id") or ""): str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
            for r in races
        }

        eb: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        entries = fetch_all(
            """
            select race_id,lane,racer_class,national_win_rate,national_place2_rate,
                   local_place2_rate,avg_st,motor_place2_rate,boat_place2_rate
            from v2_race_entries
            where race_id >= %s and race_id < %s
            order by race_id,lane
            """,
            (p, np),
        )
        for e in entries:
            rid = str(e.get("race_id") or "")
            if rid in result_map:
                eb[rid].append(e)

        for rid, win_ticket in result_map.items():
            ent = eb.get(rid, [])
            by = v24._entry_by_lane(ent)
            if len(by) != 6 or not win_ticket:
                continue
            full6 += 1
            has_motor = all(by[i].get("motor_place2_rate") is not None for i in range(1, 7))
            has_boat = all(by[i].get("boat_place2_rate") is not None for i in range(1, 7))
            motor6 += int(has_motor)
            boat6 += int(has_boat)
            if not (has_motor and has_boat):
                continue

            venue = venue_map.get(rid, "")
            base = v24._ticket_probabilities(ent, venue)
            actual = actual_ticket_probabilities(ent, venue)
            if win_ticket not in base or win_ticket not in actual:
                continue

            compare += 1
            bp = max(sf(base.get(win_ticket)), 1e-15)
            ap = max(sf(actual.get(win_ticket)), 1e-15)
            bll = -math.log(bp)
            all_ = -math.log(ap)
            base_logloss += bll
            actual_logloss += all_
            actual_ll_better += int(all_ < bll)

            bb = 0.0
            ab = 0.0
            for t in base:
                y = 1.0 if t == win_ticket else 0.0
                bb += (base[t] - y) ** 2
                ab += (actual[t] - y) ** 2
            base_brier += bb
            actual_brier += ab

            br = rank_of(base, win_ticket)
            ar = rank_of(actual, win_ticket)
            base_rank_sum += br
            actual_rank_sum += ar
            actual_rank_better += int(ar < br)
            rank_equal += int(ar == br)

            mo = ds[:7]
            monthly[mo]["n"] += 1
            monthly[mo]["base_ll"] += bll
            monthly[mo]["actual_ll"] += all_
            monthly[mo]["better"] += int(all_ < bll)

    print(f"COVERAGE=result_races:{total_results} full6:{full6} motor2_full6:{motor6} boat2_full6:{boat6} compared:{compare}", flush=True)
    if compare:
        print(
            f"LOGLOSS=baseline:{base_logloss/compare:.8f} actual_motor_boat:{actual_logloss/compare:.8f} "
            f"delta:{(actual_logloss-base_logloss)/compare:+.8f} improved_races:{actual_ll_better}/{compare}",
            flush=True,
        )
        print(
            f"BRIER=baseline:{base_brier/compare:.8f} actual_motor_boat:{actual_brier/compare:.8f} "
            f"delta:{(actual_brier-base_brier)/compare:+.8f}",
            flush=True,
        )
        print(
            f"WINNER_RANK=baseline_avg:{base_rank_sum/compare:.4f} actual_motor_boat_avg:{actual_rank_sum/compare:.4f} "
            f"actual_better:{actual_rank_better}/{compare} equal:{rank_equal}/{compare}",
            flush=True,
        )

    print("=== MONTHLY ===", flush=True)
    for mo in sorted(monthly):
        s = monthly[mo]
        n = s["n"]
        if n:
            print(
                f"{mo}: n={n} baseline_logloss={s['base_ll']/n:.8f} "
                f"actual_motor_boat_logloss={s['actual_ll']/n:.8f} "
                f"delta={(s['actual_ll']-s['base_ll'])/n:+.8f} improved={s['better']}/{n}",
                flush=True,
            )

    print("INTERPRETATION=negative_logloss_and_brier_delta_support_using_actual_motor_boat_rates_in_a_future_shadow_probability_model_only", flush=True)
    print("RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
