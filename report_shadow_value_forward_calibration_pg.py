# -*- coding: utf-8 -*-
"""
report_shadow_value_forward_calibration_pg.py

Candidate Shadow の実際の PRE 時点保存値だけを使って、
model prob * candidate odds (= value ratio) と実現成績の関係を診断する読み取り専用レポート。

重要:
- v2_candidate_filter_shadow の保存済み prob / odds / result のみ読む。
- 同一 race_id・rule_id は最新 snapshot 1件に固定。
- DB書き込みなし / LINEなし / Production判定変更なし / rule変更なし。
- raw v24 prob は絶対確率として未校正の可能性があるため、value ratio は研究指標としてのみ扱う。
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, List

from db_pg import fetch_all

VERSION = "2026-08-24 shadow-value-forward-calibration-v1"
START_DATE = os.getenv("SHADOW_VALUE_START_DATE", "2026-08-01")
END_DATE = os.getenv("SHADOW_VALUE_END_DATE", "2026-08-24")


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


def value_bucket(v: float) -> str:
    if v < 0.05: return "00_<0.05"
    if v < 0.10: return "01_0.05-0.10"
    if v < 0.20: return "02_0.10-0.20"
    if v < 0.40: return "03_0.20-0.40"
    if v < 0.70: return "04_0.40-0.70"
    if v < 1.00: return "05_0.70-1.00"
    return "06_1.00+"


def edge_bucket(prob_rank: int, market_rank: int) -> str:
    d = market_rank - prob_rank
    if d <= -10: return "00_model_worse_10p"
    if d <= -3: return "01_model_worse_3_9"
    if d <= 2: return "02_near_rank"
    if d <= 9: return "03_model_better_3_9"
    return "04_model_better_10p"


def stat() -> Dict[str, Any]:
    return {
        "n": 0, "hits": 0, "investment": 0, "ret": 0,
        "sum_prob": 0.0, "sum_odds": 0.0, "sum_vr": 0.0, "sum_raw_ev": 0.0,
    }


def add(s: Dict[str, Any], r: Dict[str, Any]) -> None:
    prob = sf(r.get("prob"))
    odds = sf(r.get("odds"))
    inv = si(r.get("investment_yen"), 100) or 100
    ret = si(r.get("return_yen"), 0)
    hit = bool(r.get("hit"))
    s["n"] += 1
    s["hits"] += int(hit)
    s["investment"] += inv
    s["ret"] += ret
    s["sum_prob"] += prob
    s["sum_odds"] += odds
    s["sum_vr"] += prob * odds
    s["sum_raw_ev"] += sf(r.get("raw_ev"))


def emit(label: str, s: Dict[str, Any]) -> None:
    n = s["n"]
    hit_rate = s["hits"] / n * 100 if n else 0.0
    roi = s["ret"] / s["investment"] * 100 if s["investment"] else 0.0
    avg_prob = s["sum_prob"] / n * 100 if n else 0.0
    avg_odds = s["sum_odds"] / n if n else 0.0
    avg_vr = s["sum_vr"] / n if n else 0.0
    avg_raw_ev = s["sum_raw_ev"] / n if n else 0.0
    print(
        f"{label}: n={n} hits={s['hits']} hit_rate={hit_rate:.2f}% "
        f"avg_prob={avg_prob:.3f}% avg_odds={avg_odds:.2f} avg_value_ratio={avg_vr:.4f} "
        f"avg_raw_ev={avg_raw_ev:.4f} investment={s['investment']} return={s['ret']} "
        f"profit={s['ret']-s['investment']} ROI={roi:.2f}%",
        flush=True,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")

    print(f"✅ report_shadow_value_forward_calibration_pg.py VERSION {VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("POLICY=read_only_frozen_candidate_values_no_production_no_line", flush=True)

    rows: List[Dict[str, Any]] = fetch_all(
        """
        with ranked as (
          select s.*,
                 row_number() over (
                   partition by race_id, rule_id
                   order by coalesce(snapshot_at, evaluated_at, updated_at, created_at) desc nulls last, id desc
                 ) as rn
          from v2_candidate_filter_shadow s
          where race_date >= %s::date
            and race_date <= %s::date
            and upper(coalesce(rule_id,'')) in ('S01','S02','S03','S04','S05','N02')
        )
        select race_id,race_date,venue_id,race_no,window_name,upper(rule_id) rule_id,
               ticket,odds,prob,prob_rank,market_rank,raw_ev,snapshot_at,
               hit,investment_yen,return_yen,evaluation_status,evaluated_at
        from ranked
        where rn=1
        order by race_date,race_id,rule_id
        """,
        (START_DATE, END_DATE),
    )

    total = len(rows)
    evaluated = [r for r in rows if str(r.get("evaluation_status") or "").lower() == "evaluated" and r.get("hit") is not None]
    pending = total - len(evaluated)
    print(f"COVERAGE=rows:{total} evaluated:{len(evaluated)} pending_or_other:{pending}", flush=True)

    print("\n=== BY RULE ===", flush=True)
    by_rule = defaultdict(stat)
    for r in evaluated:
        add(by_rule[str(r.get("rule_id") or "UNKNOWN")], r)
    for k in sorted(by_rule):
        emit(k, by_rule[k])

    print("\n=== VALUE RATIO BUCKETS: prob * frozen_candidate_odds ===", flush=True)
    by_vr = defaultdict(stat)
    for r in evaluated:
        add(by_vr[value_bucket(sf(r.get("prob")) * sf(r.get("odds")))], r)
    for k in sorted(by_vr):
        emit(k.split("_", 1)[1], by_vr[k])

    print("\n=== MODEL RANK VS MARKET RANK ===", flush=True)
    by_edge = defaultdict(stat)
    for r in evaluated:
        pr = si(r.get("prob_rank"), 999)
        mr = si(r.get("market_rank"), 999)
        if pr < 999 and mr < 999:
            add(by_edge[edge_bucket(pr, mr)], r)
    for k in sorted(by_edge):
        emit(k.split("_", 1)[1], by_edge[k])

    print("\n=== RULE x VALUE RATIO ===", flush=True)
    by_rule_vr = defaultdict(stat)
    for r in evaluated:
        rule = str(r.get("rule_id") or "UNKNOWN")
        vb = value_bucket(sf(r.get("prob")) * sf(r.get("odds"))).split("_", 1)[1]
        add(by_rule_vr[f"{rule}|{vb}"], r)
    for k in sorted(by_rule_vr):
        emit(k, by_rule_vr[k])

    print("\nINTERPRETATION=if_higher_value_ratio_or_model_better_rank_does_not_improve_realized_ROI_do_not_use_raw_v24_prob_as_Bao_theoretical_price", flush=True)
    print("RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
