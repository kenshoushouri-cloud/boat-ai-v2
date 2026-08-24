# -*- coding: utf-8 -*-
"""
backtest_prob_rank_calibration_oos_pg.py

馬王型の独立確率モデル診断。
TRAIN期間だけで「AI確率順位 -> 実際の1着組合せ発生率」を推定し、
完全に後ろのOOS期間へ固定適用する読み取り専用バックテスト。

狙い:
- raw v24 probability の絶対値が未校正でも、順位情報が有効かを確認する。
- AI評価が高いほど悪化する現象が、絶対確率の過大評価なのか順位自体の問題なのか分離する。
- PR #186で改善が確認された実測 motor2 / boat2 を Shadow 計算だけで使用する。

DB書き込みなし / LINEなし / Production変更なし / 係数探索なし / 閾値探索なし。
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24
from backtest_prob_actual_motor_shadow_pg import actual_ticket_probabilities

VERSION = "2026-08-24 prob-rank-calibration-oos-v1"
TRAIN_START = os.getenv("RANK_CAL_TRAIN_START", "2026-01-01")
TRAIN_END = os.getenv("RANK_CAL_TRAIN_END", "2026-06-30")
OOS_START = os.getenv("RANK_CAL_OOS_START", "2026-07-01")
OOS_END = os.getenv("RANK_CAL_OOS_END", "2026-08-15")
UNIT_YEN = 100

RANK_BUCKETS: List[Tuple[str, int, int]] = [
    ("R01_03", 1, 3),
    ("R04_06", 4, 6),
    ("R07_10", 7, 10),
    ("R11_20", 11, 20),
    ("R21_40", 21, 40),
    ("R41_80", 41, 80),
    ("R81_120", 81, 120),
]


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


def rank_bucket(rank: int) -> str:
    for name, lo, hi in RANK_BUCKETS:
        if lo <= rank <= hi:
            return name
    return "UNKNOWN"


def value_bucket(v: float) -> str:
    if v < 0.8: return "00_<0.8"
    if v < 1.0: return "01_0.8-1.0"
    if v < 1.2: return "02_1.0-1.2"
    if v < 1.5: return "03_1.2-1.5"
    if v < 2.0: return "04_1.5-2.0"
    return "05_2.0+"


def period_prefix(date_str: str) -> str:
    return date_str.replace("-", "")


def next_day_prefix(date_str: str) -> str:
    from datetime import datetime, timedelta
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")


def fetch_period(start: str, end: str, with_odds: bool = False):
    results = fetch_all(
        """
        select race_id,race_date,trifecta_ticket,trifecta_payout_yen
        from v2_results
        where race_date >= %s::date and race_date <= %s::date
          and trifecta_ticket is not null
          and trifecta_payout_yen is not null
          and trifecta_payout_yen > 0
          and coalesce(result_status,'')='official'
          and coalesce(race_status,'')='official'
        order by race_date,race_id
        """,
        (start, end),
    )
    result_by = {str(r.get("race_id") or ""): r for r in results if r.get("race_id")}
    ids = set(result_by)

    races = fetch_all(
        """
        select race_id,race_date,venue_id,venue_code
        from v2_races
        where race_date >= %s::date and race_date <= %s::date
        order by race_date,venue_id,race_id
        """,
        (start, end),
    )
    venue_by = {
        str(r.get("race_id") or ""): str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
        for r in races if str(r.get("race_id") or "") in ids
    }

    entries_by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in fetch_all(
        """
        select race_id,lane,racer_class,national_win_rate,national_place2_rate,
               local_place2_rate,avg_st,motor_place2_rate,boat_place2_rate
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id,lane
        """,
        (period_prefix(start), next_day_prefix(end)),
    ):
        rid = str(e.get("race_id") or "")
        if rid in ids:
            entries_by[rid].append(e)

    odds_by: Dict[str, Dict[str, float]] = defaultdict(dict)
    if with_odds:
        for o in fetch_all(
            """
            select race_id,ticket,odds
            from v2_odds_trifecta
            where race_id >= %s and race_id < %s
            order by race_id,ticket
            """,
            (period_prefix(start), next_day_prefix(end)),
        ):
            rid = str(o.get("race_id") or "")
            if rid not in ids:
                continue
            ticket = v24._norm_ticket(o.get("ticket"))
            odd = sf(o.get("odds"))
            if ticket and odd > 0:
                odds_by[rid][ticket] = odd

    return result_by, venue_by, entries_by, odds_by


def eligible(entries: List[Dict[str, Any]]) -> bool:
    by = v24._entry_by_lane(entries)
    if len(by) != 6:
        return False
    return all(
        by[lane].get("motor_place2_rate") is not None
        and by[lane].get("boat_place2_rate") is not None
        for lane in range(1, 7)
    )


def ordered_probs(entries: List[Dict[str, Any]], venue: str):
    probs = actual_ticket_probabilities(entries, venue)
    ordered = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    rank_by = {ticket: i for i, (ticket, _) in enumerate(ordered, 1)}
    return probs, ordered, rank_by


def stat() -> Dict[str, Any]:
    return {"n":0,"hits":0,"investment":0,"ret":0,"sum_v":0.0,"sum_odds":0.0}


def add_bet(s: Dict[str, Any], hit: bool, payout: int, value: float, odds: float) -> None:
    s["n"] += 1
    s["hits"] += int(hit)
    s["investment"] += UNIT_YEN
    if hit:
        s["ret"] += payout
    s["sum_v"] += value
    s["sum_odds"] += odds


def emit_bet(label: str, s: Dict[str, Any]) -> None:
    n = s["n"]
    hr = s["hits"] / n * 100 if n else 0.0
    roi = s["ret"] / s["investment"] * 100 if s["investment"] else 0.0
    av = s["sum_v"] / n if n else 0.0
    ao = s["sum_odds"] / n if n else 0.0
    print(
        f"{label}: n={n} hits={s['hits']} hit_rate={hr:.3f}% avg_value={av:.4f} "
        f"avg_odds={ao:.2f} investment={s['investment']} return={s['ret']} "
        f"profit={s['ret']-s['investment']} ROI={roi:.2f}%",
        flush=True,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")

    print(f"✅ backtest_prob_rank_calibration_oos_pg.py VERSION {VERSION}", flush=True)
    print(f"TRAIN={TRAIN_START}..{TRAIN_END} OOS={OOS_START}..{OOS_END}", flush=True)
    print("MODEL=actual_motor_boat_shadow_fixed_formula", flush=True)
    print("POLICY=train_rank_frequency_then_fixed_oos_no_tuning_no_production_no_line", flush=True)

    tr_res, tr_venue, tr_entries, _ = fetch_period(TRAIN_START, TRAIN_END, False)
    bucket_exposure = defaultdict(int)
    bucket_hits = defaultdict(int)
    train_used = 0

    for rid, res in tr_res.items():
        entries = tr_entries.get(rid, [])
        if not eligible(entries):
            continue
        win = v24._norm_ticket(res.get("trifecta_ticket"))
        venue = tr_venue.get(rid, "")
        probs, ordered, rank_by = ordered_probs(entries, venue)
        if win not in probs:
            continue
        train_used += 1
        for name, lo, hi in RANK_BUCKETS:
            bucket_exposure[name] += (hi - lo + 1)
        bucket_hits[rank_bucket(rank_by[win])] += 1

    empirical_p: Dict[str, float] = {}
    print("\n=== TRAIN RANK CALIBRATION ===", flush=True)
    print(f"TRAIN_COVERAGE=result_races:{len(tr_res)} used:{train_used}", flush=True)
    mass = 0.0
    for name, lo, hi in RANK_BUCKETS:
        exp = bucket_exposure[name]
        hits = bucket_hits[name]
        p = hits / exp if exp else 0.0
        empirical_p[name] = p
        bucket_size = hi - lo + 1
        bucket_mass = p * bucket_size
        mass += bucket_mass
        print(
            f"{name}: ranks={lo}-{hi} exposures={exp} winner_hits={hits} "
            f"per_ticket_prob={p*100:.5f}% bucket_mass={bucket_mass*100:.3f}%",
            flush=True,
        )
    print(f"TRAIN_EMPIRICAL_TOTAL_MASS={mass:.8f}", flush=True)

    oo_res, oo_venue, oo_entries, oo_odds = fetch_period(OOS_START, OOS_END, True)
    used = odds_ready = 0
    raw_ll = cal_ll = 0.0
    raw_brier = cal_brier = 0.0
    raw_rank_sum = 0
    winner_bucket = defaultdict(int)
    raw_top = defaultdict(stat)
    cal_top = defaultdict(stat)

    # rank bucket probabilities learned on train sum to 1 by construction (up to sample noise exactly from one winner/race).
    # Normalize tiny finite-sample drift once, without OOS information.
    norm = sum(empirical_p[name] * (hi-lo+1) for name, lo, hi in RANK_BUCKETS)
    fixed_p = {k: (v / norm if norm > 0 else 0.0) for k, v in empirical_p.items()}

    for rid, res in oo_res.items():
        entries = oo_entries.get(rid, [])
        if not eligible(entries):
            continue
        win = v24._norm_ticket(res.get("trifecta_ticket"))
        payout = si(res.get("trifecta_payout_yen"))
        venue = oo_venue.get(rid, "")
        probs, ordered, rank_by = ordered_probs(entries, venue)
        if win not in probs:
            continue
        used += 1
        wr = rank_by[win]
        raw_rank_sum += wr
        winner_bucket[rank_bucket(wr)] += 1

        rp = max(sf(probs.get(win)), 1e-15)
        cp = max(fixed_p.get(rank_bucket(wr), 0.0), 1e-15)
        raw_ll += -math.log(rp)
        cal_ll += -math.log(cp)

        rb = 0.0
        cb = 0.0
        for ticket, p in probs.items():
            y = 1.0 if ticket == win else 0.0
            rb += (p-y)**2
            rank = rank_by[ticket]
            q = fixed_p.get(rank_bucket(rank), 0.0)
            cb += (q-y)**2
        raw_brier += rb
        cal_brier += cb

        odds = oo_odds.get(rid, {})
        ok, _ = v24._validate_odds_snapshot(odds)
        if len(odds) != 120 or not ok:
            continue
        odds_ready += 1

        raw_best = None
        cal_best = None
        for ticket, p in probs.items():
            odd = sf(odds.get(ticket))
            if odd <= 0:
                continue
            rank = rank_by[ticket]
            raw_v = p * odd
            cal_v = fixed_p.get(rank_bucket(rank), 0.0) * odd
            if raw_best is None or raw_v > raw_best[0]:
                raw_best = (raw_v, ticket, odd)
            if cal_best is None or cal_v > cal_best[0]:
                cal_best = (cal_v, ticket, odd)

        if raw_best:
            v, ticket, odd = raw_best
            add_bet(raw_top[value_bucket(v)], ticket == win, payout, v, odd)
        if cal_best:
            v, ticket, odd = cal_best
            add_bet(cal_top[value_bucket(v)], ticket == win, payout, v, odd)

    print("\n=== OOS PROBABILITY QUALITY ===", flush=True)
    print(f"OOS_COVERAGE=result_races:{len(oo_res)} used:{used} odds_ready:{odds_ready}", flush=True)
    print(
        f"LOGLOSS=raw_actual_motor:{raw_ll/used if used else 0:.8f} "
        f"rank_calibrated:{cal_ll/used if used else 0:.8f} "
        f"delta:{(cal_ll-raw_ll)/used if used else 0:+.8f}",
        flush=True,
    )
    print(
        f"BRIER=raw_actual_motor:{raw_brier/used if used else 0:.8f} "
        f"rank_calibrated:{cal_brier/used if used else 0:.8f} "
        f"delta:{(cal_brier-raw_brier)/used if used else 0:+.8f}",
        flush=True,
    )
    print(f"WINNER_RANK_AVG={raw_rank_sum/used if used else 0:.4f}", flush=True)

    print("\n=== OOS WINNER BY AI RANK BUCKET ===", flush=True)
    for name, lo, hi in RANK_BUCKETS:
        hits = winner_bucket[name]
        rate = hits / used * 100 if used else 0.0
        print(f"{name}: winner_races={hits}/{used} race_share={rate:.3f}%", flush=True)

    print("\n=== RAW PROB TOP VALUE PER RACE ===", flush=True)
    for k in sorted(raw_top):
        emit_bet(k.split("_",1)[1], raw_top[k])

    print("\n=== RANK-CALIBRATED TOP VALUE PER RACE ===", flush=True)
    for k in sorted(cal_top):
        emit_bet(k.split("_",1)[1], cal_top[k])

    print("\nINTERPRETATION=rank_calibration_improves_probability_quality_if_delta_negative; value ROI is historical-base-odds reference only and must not activate a betting rule", flush=True)
    print("HISTORICAL_ODDS_CAVEAT=v2_odds_trifecta_not_guaranteed_frozen_exact_PRE", flush=True)
    print("RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
