# -*- coding: utf-8 -*-
"""
backtest_prob_calibration_pg.py

v24_probability_model の prob を絶対確率として診断する読み取り専用バックテスト。
DB書き込みなし / LINE通知なし / 本番判定変更なし / N02条件変更なし。
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24
import collect_candidate_filter_shadow_pg as shadow

VERSION = "2026-08-18 prob-calibration-v1"
START_DATE = os.getenv("BACKTEST_START_DATE", "2025-07-01")
END_DATE = os.getenv("BACKTEST_END_DATE", "2026-08-16")
UNIT_YEN = max(1, int(os.getenv("BACKTEST_UNIT_YEN", "100")))
PROGRESS_EVERY_DAYS = max(1, int(os.getenv("BACKTEST_PROGRESS_EVERY_DAYS", "10")))

RULES_BY_ID = {str(r["rule_id"]).upper(): r for r in shadow.RULES}
N02_RULE = RULES_BY_ID["N02"]


def _si(v: Any, d: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else d
    except Exception:
        return d


def _sf(v: Any, d: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else d
    except Exception:
        return d


def _dates(a: str, b: str) -> Iterable[str]:
    d = datetime.strptime(a, "%Y-%m-%d")
    e = datetime.strptime(b, "%Y-%m-%d")
    while d <= e:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


def _stat() -> Dict[str, Any]:
    return {
        "bets": 0, "hits": 0, "investment": 0, "return": 0,
        "sum_model_prob": 0.0, "sum_market_prob": 0.0,
        "sum_odds": 0.0, "sum_value_ratio": 0.0,
    }


def _add(s: Dict[str, Any], hit: bool, payout: int, prob: float, market_prob: float, odds: float) -> None:
    s["bets"] += 1
    s["investment"] += UNIT_YEN
    s["sum_model_prob"] += prob
    s["sum_market_prob"] += market_prob
    s["sum_odds"] += odds
    s["sum_value_ratio"] += prob * odds
    if hit:
        s["hits"] += 1
        s["return"] += payout


def _print(label: str, s: Dict[str, Any]) -> None:
    b, h = s["bets"], s["hits"]
    inv, ret = s["investment"], s["return"]
    hit_rate = h / b * 100 if b else 0.0
    avg_prob = s["sum_model_prob"] / b * 100 if b else 0.0
    avg_mkt = s["sum_market_prob"] / b * 100 if b else 0.0
    avg_odds = s["sum_odds"] / b if b else 0.0
    avg_vr = s["sum_value_ratio"] / b if b else 0.0
    roi = ret / inv * 100 if inv else 0.0
    print(
        f"{label}: bets={b} hits={h} hit_rate={hit_rate:.4f}% "
        f"avg_model_prob={avg_prob:.4f}% cal_gap={hit_rate-avg_prob:+.4f}pt "
        f"avg_market_prob={avg_mkt:.4f}% avg_odds={avg_odds:.3f} "
        f"avg_value_ratio={avg_vr:.4f} investment={inv} return={ret} "
        f"profit={ret-inv} ROI={roi:.2f}%",
        flush=True,
    )


def _prob_bucket(p: float) -> str:
    x = p * 100
    if x < 0.5: return "00_0.0-0.5%"
    if x < 1.0: return "01_0.5-1.0%"
    if x < 1.5: return "02_1.0-1.5%"
    if x < 2.0: return "03_1.5-2.0%"
    if x < 3.0: return "04_2.0-3.0%"
    if x < 5.0: return "05_3.0-5.0%"
    if x < 10.0: return "06_5.0-10.0%"
    return "07_10.0%+"


def _value_bucket(v: float) -> str:
    if v < 0.8: return "00_<0.8"
    if v < 0.9: return "01_0.8-0.9"
    if v < 1.0: return "02_0.9-1.0"
    if v < 1.1: return "03_1.0-1.1"
    if v < 1.2: return "04_1.1-1.2"
    if v < 1.5: return "05_1.2-1.5"
    return "06_1.5+"


def _edge_bucket(edge: float) -> str:
    pt = edge * 100
    if pt < -2: return "00_<-2pt"
    if pt < -1: return "01_-2--1pt"
    if pt < -0.5: return "02_-1--0.5pt"
    if pt < 0: return "03_-0.5-0pt"
    if pt < 0.5: return "04_0-0.5pt"
    if pt < 1: return "05_0.5-1pt"
    if pt < 2: return "06_1-2pt"
    return "07_2pt+"


def _fetch_day(ds: str):
    p = ds.replace("-", "")
    np = (datetime.strptime(ds, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")

    results = fetch_all("""
        select race_id,trifecta_ticket,trifecta_payout_yen
        from v2_results
        where race_date=%s
          and trifecta_ticket is not null
          and trifecta_payout_yen is not null
          and trifecta_payout_yen>0
          and finish_order is not null
          and winning_method is not null
          and coalesce(result_status,'')='official'
          and coalesce(race_status,'')='official'
        order by race_id
    """, (ds,))
    rb = {str(r["race_id"]): r for r in results if r.get("race_id")}
    ids = set(rb)
    if not ids:
        return [], {}, {}, {}, {}

    races = [r for r in fetch_all(
        "select * from v2_races where race_date=%s order by venue_id,race_no", (ds,)
    ) if str(r.get("race_id") or "") in ids]

    eb: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in fetch_all("""
        select race_id,lane,racer_number,racer_class,racer_name,
               national_win_rate,national_place2_rate,local_win_rate,local_place2_rate,
               motor_no,boat_no,avg_st
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id,lane
    """, (p, np)):
        rid = str(r.get("race_id") or "")
        if rid in ids:
            eb[rid].append(r)

    ob: Dict[str, Dict[str, float]] = defaultdict(dict)
    for r in fetch_all(
        "select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s order by race_id,ticket",
        (p, np),
    ):
        rid = str(r.get("race_id") or "")
        if rid not in ids:
            continue
        t = v24._norm_ticket(r.get("ticket"))
        odd = _sf(r.get("odds"))
        if t and odd > 0:
            ob[rid][t] = odd

    kc = {}
    for r in fetch_all(
        "select race_id,count(*)::int as n from v2_result_entries where race_id >= %s and race_id < %s group by race_id",
        (p, np),
    ):
        kc[str(r.get("race_id"))] = _si(r.get("n"))

    return races, eb, ob, rb, kc


def _market_probs(odds: Dict[str, float]) -> Dict[str, float]:
    inv = {t: 1.0/o for t, o in odds.items() if o > 0}
    total = sum(inv.values())
    return {t: x/total for t, x in inv.items()} if total > 0 else {}


def main() -> None:
    print(f"✅ backtest_prob_calibration_pg.py VERSION {VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE} UNIT_YEN={UNIT_YEN}", flush=True)
    print("DB書き込みなし。LINE通知なし。本番判定変更なし。N02条件変更なし。", flush=True)
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    calib = defaultdict(_stat)
    vr_stats = defaultdict(_stat)
    edge_stats = defaultdict(_stat)
    n02 = _stat()
    n02_month = defaultdict(_stat)
    n02_prob = defaultdict(_stat)
    n02_vr = defaultdict(_stat)

    result_candidate_races = ready = skipped_entries = skipped_k = skipped_odds = ticket_rows = 0
    brier_sum = logloss_sum = 0.0

    days = list(_dates(START_DATE, END_DATE))
    for i, day in enumerate(days, 1):
        races, eb, ob, rb, kc = _fetch_day(day)
        result_candidate_races += len(races)

        for race in races:
            rid = str(race.get("race_id") or "")
            vid = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            rno = _si(race.get("race_no"))
            entries = eb.get(rid, [])
            if len(v24._entry_by_lane(entries)) != 6:
                skipped_entries += 1
                continue
            if kc.get(rid, 0) != 6:
                skipped_k += 1
                continue
            odds = ob.get(rid, {})
            ok, _ = v24._validate_odds_snapshot(odds)
            if len(odds) != 120 or not ok:
                skipped_odds += 1
                continue

            ready += 1
            res = rb[rid]
            win_ticket = v24._norm_ticket(res.get("trifecta_ticket"))
            payout = _si(res.get("trifecta_payout_yen"))
            ranked = v24._rank_candidates(entries, vid, odds)
            mp = _market_probs(odds)

            brier = 0.0
            winner_prob = 0.0
            for row in ranked:
                ticket = str(row.get("ticket") or "")
                prob = _sf(row.get("prob"))
                odd = _sf(row.get("odds"))
                mprob = _sf(mp.get(ticket))
                hit = ticket == win_ticket
                if hit:
                    winner_prob = prob
                brier += (prob - (1.0 if hit else 0.0)) ** 2
                _add(calib[_prob_bucket(prob)], hit, payout, prob, mprob, odd)
                _add(vr_stats[_value_bucket(prob*odd)], hit, payout, prob, mprob, odd)
                _add(edge_stats[_edge_bucket(prob-mprob)], hit, payout, prob, mprob, odd)
                ticket_rows += 1

            brier_sum += brier
            logloss_sum += -math.log(max(winner_prob, 1e-15))

            vs = v24._infer_venue_style(vid)
            ec = v24._infer_event_category(v24._metadata_text(race))
            rule = N02_RULE
            if rno not in rule["race_nos"]:
                continue
            if rule["venue_style"] != "ALL" and vs != rule["venue_style"]:
                continue
            if rule["event_category"] != "ALL" and ec != rule["event_category"]:
                continue
            matches = [x for x in ranked if shadow._match_rule(x, rule)]
            sel = shadow._select_one(matches, str(rule["select_mode"]))
            if not sel:
                continue
            ticket = str(sel.get("ticket") or "")
            if not ticket:
                continue
            prob = _sf(sel.get("prob"))
            odd = _sf(sel.get("odds"))
            mprob = _sf(mp.get(ticket))
            hit = ticket == win_ticket
            _add(n02, hit, payout, prob, mprob, odd)
            _add(n02_month[day[:7]], hit, payout, prob, mprob, odd)
            _add(n02_prob[_prob_bucket(prob)], hit, payout, prob, mprob, odd)
            _add(n02_vr[_value_bucket(prob*odd)], hit, payout, prob, mprob, odd)

        if i % PROGRESS_EVERY_DAYS == 0 or i == len(days):
            print(f"PROGRESS {i}/{len(days)} date={day} ready_races={ready} ticket_rows={ticket_rows} N02={n02['bets']}", flush=True)

    weighted_gap = 0.0
    weighted_n = 0
    for s in calib.values():
        b = s["bets"]
        if not b:
            continue
        weighted_gap += abs(s["sum_model_prob"]/b - s["hits"]/b) * b
        weighted_n += b
    ece = weighted_gap / weighted_n * 100 if weighted_n else 0.0

    print("\n=== AUDIT SUMMARY ===", flush=True)
    print(f"result_candidate_races={result_candidate_races}", flush=True)
    print(f"ready_races={ready}", flush=True)
    print(f"skipped_entries={skipped_entries}", flush=True)
    print(f"skipped_k={skipped_k}", flush=True)
    print(f"skipped_odds={skipped_odds}", flush=True)
    print(f"ticket_rows={ticket_rows}", flush=True)

    print("\n=== MODEL QUALITY ===", flush=True)
    print(f"avg_multiclass_brier_per_race={brier_sum/ready if ready else 0:.8f}", flush=True)
    print(f"avg_winner_logloss={logloss_sum/ready if ready else 0:.8f}", flush=True)
    print(f"bucket_ECE={ece:.6f}pt", flush=True)

    print("\n=== PROB CALIBRATION ===", flush=True)
    for k in sorted(calib): _print(k.split("_",1)[1], calib[k])

    print("\n=== VALUE RATIO: model_prob * odds ===", flush=True)
    print("各ticketを100円ずつ買った場合の診断値。購入戦略そのものではありません。", flush=True)
    for k in sorted(vr_stats): _print(k.split("_",1)[1], vr_stats[k])

    print("\n=== MODEL - NORMALIZED MARKET PROB EDGE ===", flush=True)
    for k in sorted(edge_stats): _print(k.split("_",1)[1], edge_stats[k])

    print("\n=== N02 CALIBRATION ===", flush=True)
    _print("N02 ALL", n02)

    print("\n=== N02 x MONTH ===", flush=True)
    for k in sorted(n02_month): _print(f"N02 {k}", n02_month[k])

    print("\n=== N02 x MODEL PROB BUCKET ===", flush=True)
    for k in sorted(n02_prob): _print(f"N02 {k.split('_',1)[1]}", n02_prob[k])

    print("\n=== N02 x VALUE RATIO ===", flush=True)
    for k in sorted(n02_vr): _print(f"N02 {k.split('_',1)[1]}", n02_vr[k])

    print("\n=== INTERPRETATION GUIDE ===", flush=True)
    print("avg_model_prob と hit_rate が近いほど絶対確率の校正が良好。", flush=True)
    print("value_ratio が高いほどROIも上がるなら馬王型の理論価格アプローチに追い風。", flush=True)
    print("prob絶対値がズレてもN02が強ければ、順位付け能力が残っている可能性あり。", flush=True)
    print("この結果だけで条件変更せず、次に期間分割・Walk-forwardで再検証する。", flush=True)
    print("RESULT=PASS", flush=True)

if __name__ == "__main__":
    main()