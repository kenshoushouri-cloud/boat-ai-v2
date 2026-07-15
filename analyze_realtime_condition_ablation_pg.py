# -*- coding: utf-8 -*-
"""
analyze_realtime_condition_ablation_pg.py

当日コンディション特徴量を分解し、どの項目・重みが効くか比較します。
読み取り専用です。本番判定・LINE通知・購入処理は変更しません。

比較対象:
- baseline
- 前走STのみ
- 調整重量のみ
- 前走着順のみ
- 前走進入一致のみ
- 部品/新プロペラのみ
- 軽量combined
- 現行combined

Start Command:
    python -u analyze_realtime_condition_ablation_pg.py
"""

from __future__ import annotations

import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all
import v22_realtime_decision_engine_pg as base

JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
MIN_CONDITION_COVERAGE = int(os.getenv("MIN_CONDITION_COVERAGE", "6"))


def sf(v: Any, d: float = 0.0) -> float:
    try:
        return d if v is None or v == "" else float(v)
    except Exception:
        return d


def si(v: Any, d: int = 0) -> int:
    try:
        return d if v is None or v == "" else int(float(v))
    except Exception:
        return d


def norm_ticket(v: Any) -> str:
    nums = re.findall(r"[1-6]", str(v or ""))
    return f"{nums[0]}-{nums[1]}-{nums[2]}" if len(nums) >= 3 else ""


def result_ticket(row: Dict[str, Any]) -> str:
    for key in ("result_trifecta", "trifecta", "winning_ticket", "result", "finish_order"):
        t = norm_ticket(row.get(key))
        if t:
            return t
    a = si(row.get("first_lane") or row.get("first") or row.get("rank1"))
    b = si(row.get("second_lane") or row.get("second") or row.get("rank2"))
    c = si(row.get("third_lane") or row.get("third") or row.get("rank3"))
    return f"{a}-{b}-{c}" if all(1 <= x <= 6 for x in (a, b, c)) else ""


def rank_rows(
    entries: List[Dict[str, Any]],
    venue: str,
    odds: Dict[str, float],
    conds: Dict[int, Dict[str, Any]],
    config: Dict[str, float],
) -> List[Dict[str, Any]]:
    by = base._entry_by_lane(entries)
    raw = {}

    for lane in range(1, 7):
        score = base._lane_raw_strength(by[lane], lane, venue)
        cond = conds.get(lane, {})

        if config.get("prev_st", 0.0) and cond.get("previous_st") is not None:
            st = sf(cond.get("previous_st"), 0.18)
            st_adj = 0.0
            if st <= 0.10:
                st_adj = 1.0
            elif st <= 0.15:
                st_adj = 0.5
            elif st >= 0.25:
                st_adj = -0.75
            elif st >= 0.20:
                st_adj = -0.4
            score += st_adj * config["prev_st"]

        if config.get("adjustment", 0.0):
            aw = sf(cond.get("adjustment_weight_kg"), 0.0)
            aw_adj = -1.0 if aw >= 2.0 else -0.5 if aw >= 1.0 else 0.0
            score += aw_adj * config["adjustment"]

        if config.get("finish", 0.0):
            finish = si(cond.get("previous_finish"), 0)
            f_adj = 1.0 if finish == 1 else 0.5 if finish == 2 else -0.5 if finish >= 5 else 0.0
            score += f_adj * config["finish"]

        if config.get("same_course", 0.0):
            pc = si(cond.get("previous_course"), 0)
            if pc and pc == lane:
                score += config["same_course"]

        if config.get("parts", 0.0):
            parts = cond.get("parts_replacements") or []
            if parts:
                score -= config["parts"]
            if cond.get("is_new_propeller"):
                score -= config["parts"] * 1.5

        raw[lane] = score

    weights = {lane: math.exp(raw[lane] / base.PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    rows = []

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
                ticket = f"{a}-{b}-{c}"
                odd = sf(odds.get(ticket), 0.0)
                if odd <= 0:
                    continue
                prob = pa * pb * (weights[c] / tc)
                rows.append({"ticket": ticket, "prob": prob, "odds": odd})

    for i, r in enumerate(sorted(rows, key=lambda x: (x["odds"], -x["prob"])), 1):
        r["market_rank"] = i
    for i, r in enumerate(sorted(rows, key=lambda x: x["prob"], reverse=True), 1):
        r["prob_rank"] = i
    return rows


def summarize(name: str, ranks: List[int]) -> Tuple[float, float, float]:
    n = len(ranks)
    avg = sum(ranks) / n
    top5 = sum(r <= 5 for r in ranks) / n * 100
    top10 = sum(r <= 10 for r in ranks) / n * 100
    top20 = sum(r <= 20 for r in ranks) / n * 100
    print(
        f"{name}: races={n} avg={avg:.3f} "
        f"top5={top5:.2f}% top10={top10:.2f}% top20={top20:.2f}%",
        flush=True,
    )
    return avg, top5, top10


def main() -> None:
    print(
        "✅ analyze_realtime_condition_ablation_pg.py "
        "VERSION 2026-07-15 ablation-v1",
        flush=True,
    )
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(
        f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"MIN_CONDITION_COVERAGE={MIN_CONDITION_COVERAGE}",
        flush=True,
    )
    print("読み取り専用です。本番判定・LINE通知は変更しません。", flush=True)

    races = fetch_all(
        "select * from v2_races where race_date=%s order by venue_id,race_no;",
        (TARGET_DATE,),
    )
    race_ids = [str(r.get("race_id")) for r in races]

    entries_rows = fetch_all(
        "select * from v2_race_entries where race_id=any(%s) order by race_id,lane;",
        (race_ids,),
    )
    entries_by: Dict[str, List[Dict[str, Any]]] = {}
    for r in entries_rows:
        entries_by.setdefault(str(r.get("race_id")), []).append(r)

    odds_rows = fetch_all(
        "select race_id,ticket,odds from v2_odds_trifecta where race_id=any(%s);",
        (race_ids,),
    )
    odds_by: Dict[str, Dict[str, float]] = {}
    for r in odds_rows:
        t = norm_ticket(r.get("ticket"))
        o = sf(r.get("odds"), 0.0)
        if t and o > 0:
            odds_by.setdefault(str(r.get("race_id")), {})[t] = o

    cond_rows = fetch_all(
        """
        select *
        from v2_realtime_racer_condition_snapshots
        where race_id=any(%s) and snapshot_label=%s
        order by race_id,lane;
        """,
        (race_ids, SNAPSHOT_LABEL),
    )
    cond_by: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for r in cond_rows:
        cond_by.setdefault(str(r.get("race_id")), {})[si(r.get("lane"))] = r

    next_date = (datetime.strptime(TARGET_DATE, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
    result_rows = fetch_all(
        "select * from v2_results where race_id >= %s and race_id < %s;",
        (TARGET_DATE.replace("-", ""), next_date),
    )
    results = {str(r.get("race_id")): result_ticket(r) for r in result_rows}
    results = {k: v for k, v in results.items() if v}

    configs = {
        "BASELINE": {},
        "ST_005": {"prev_st": 0.05},
        "ST_010": {"prev_st": 0.10},
        "ST_015": {"prev_st": 0.15},
        "ADJ_005": {"adjustment": 0.05},
        "ADJ_010": {"adjustment": 0.10},
        "FINISH_005": {"finish": 0.05},
        "FINISH_010": {"finish": 0.10},
        "SAME_COURSE_003": {"same_course": 0.03},
        "PARTS_005": {"parts": 0.05},
        "COMBINED_LIGHT": {
            "prev_st": 0.05,
            "adjustment": 0.03,
            "finish": 0.03,
            "same_course": 0.01,
            "parts": 0.03,
        },
        "COMBINED_MEDIUM": {
            "prev_st": 0.10,
            "adjustment": 0.05,
            "finish": 0.05,
            "same_course": 0.02,
            "parts": 0.05,
        },
    }

    ranks_by_config = {name: [] for name in configs}
    eligible = 0

    for race in races:
        rid = str(race.get("race_id"))
        entries = entries_by.get(rid, [])
        odds = odds_by.get(rid, {})
        conds = cond_by.get(rid, {})
        winning = results.get(rid)

        if (
            len(base._entry_by_lane(entries)) != 6
            or len(odds) < 100
            or len(conds) < MIN_CONDITION_COVERAGE
            or not winning
        ):
            continue

        eligible += 1
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)

        for name, cfg in configs.items():
            rows = rank_rows(entries, venue, odds, conds, cfg)
            rank_map = {r["ticket"]: si(r.get("prob_rank"), 999) for r in rows}
            if winning in rank_map:
                ranks_by_config[name].append(rank_map[winning])

    print(f"eligible_races={eligible}", flush=True)
    metrics = {}
    for name in configs:
        metrics[name] = summarize(name, ranks_by_config[name])

    base_avg, base_top5, base_top10 = metrics["BASELINE"]
    print("\n=== RANKED CONFIGS ===", flush=True)
    scored = []
    for name, (avg, top5, top10) in metrics.items():
        if name == "BASELINE":
            continue
        score = (base_avg - avg) + (top5 - base_top5) * 0.20 + (top10 - base_top10) * 0.10
        scored.append((score, name, avg, top5, top10))

    for i, (score, name, avg, top5, top10) in enumerate(
        sorted(scored, reverse=True), 1
    ):
        print(
            f"{i:02d}. {name} score={score:+.3f} "
            f"avg={avg:.3f} top5={top5:.2f}% top10={top10:.2f}%",
            flush=True,
        )

    print(
        "判定目安: 平均順位とTop5/Top10が同時改善する設定だけを次候補にする。",
        flush=True,
    )
    print("=== realtime condition ablation finished ===", flush=True)


if __name__ == "__main__":
    main()