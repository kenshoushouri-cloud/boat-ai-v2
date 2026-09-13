# -*- coding: utf-8 -*-
"""Pure metrics for exact V4 MKT_LATE07_TOP2_SUPPORT_V1 Forward evidence.

No DB/network access. The caller supplies already-frozen annotation rows joined
later with official trifecta outcome returns. This module only summarizes the
same-universe late baseline and market-TOP2-supported subset.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

UNIT_YEN = 100
MILESTONES = (30, 50, 100)


def _ordered(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda x: (
        str(x.get("race_date") or ""),
        str(x.get("venue_id") or ""),
        int(x.get("race_no") or 0),
        str(x.get("race_id") or ""),
    ))


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = _ordered(rows)
    n = len(ordered)
    hits = 0
    ret = 0
    losing = 0
    max_losing = 0
    running = 0
    peak = 0
    max_dd = 0
    hit_returns: list[int] = []
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in ordered:
        value = int(row.get("return_yen") or 0)
        hit = bool(row.get("hit"))
        if hit:
            hits += 1
            losing = 0
            hit_returns.append(value)
        else:
            losing += 1
            max_losing = max(max_losing, losing)
        ret += value
        running += value - UNIT_YEN
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
        by_day[str(row.get("race_date") or "")].append(row)

    positive_days = 0
    for day_rows in by_day.values():
        day_ret = sum(int(x.get("return_yen") or 0) for x in day_rows)
        day_inv = UNIT_YEN * len(day_rows)
        if day_ret > day_inv:
            positive_days += 1

    inv = n * UNIT_YEN
    max_hit = max(hit_returns) if hit_returns else 0
    return {
        "evaluated_cases": n,
        "evaluated_days": len(by_day),
        "hits": hits,
        "hit_rate_pct": round(hits / n * 100.0, 3) if n else None,
        "investment_yen": inv,
        "return_yen": ret,
        "profit_yen": ret - inv,
        "roi_pct": round(ret / inv * 100.0, 3) if inv else None,
        "max_losing_race_streak": max_losing,
        "max_drawdown_yen": max_dd,
        "positive_days": positive_days,
        "positive_day_rate_pct": round(positive_days / len(by_day) * 100.0, 3) if by_day else None,
        "max_single_hit_return_yen": max_hit,
        "max_single_hit_share_of_returns_pct": round(max_hit / ret * 100.0, 3) if ret else None,
    }


def _milestone_state(n: int) -> dict[str, Any]:
    reached = [m for m in MILESTONES if n >= m]
    next_target = next((m for m in MILESTONES if n < m), None)
    return {
        "supported_evaluated_cases": n,
        "reached": reached,
        "next_target": next_target,
        "remaining_to_next": (next_target - n) if next_target is not None else 0,
        "promotion_allowed": False,
    }


def summarize_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize prospective exact-V4 trifecta records.

    Each input row is one immutable V4 core TOP1 race. Required flags:
    counts_as_prospective, late_snapshot_available, result_ready,
    market_top2_support, hit, return_yen.
    """
    seen: set[str] = set()
    prospective_ready: list[dict[str, Any]] = []
    for row in rows:
        rid = str(row.get("race_id") or "")
        if not rid:
            raise ValueError("race_id required")
        if rid in seen:
            raise ValueError(f"duplicate race_id: {rid}")
        seen.add(rid)
        if not bool(row.get("counts_as_prospective")):
            continue
        if not bool(row.get("late_snapshot_available")):
            continue
        if not bool(row.get("result_ready")):
            continue
        value = int(row.get("return_yen") or 0)
        if value < 0:
            raise ValueError("return_yen cannot be negative")
        hit = bool(row.get("hit"))
        if not hit and value != 0:
            raise ValueError("non-hit must have zero return")
        if hit and value <= 0:
            raise ValueError("hit must have positive return")
        prospective_ready.append(dict(row))

    baseline = prospective_ready
    supported = [x for x in prospective_ready if bool(x.get("market_top2_support"))]
    return {
        "contract": "MKT_LATE07_TOP2_SUPPORT_V1_FORWARD_METRICS",
        "bet_type": "trifecta",
        "unit_yen": UNIT_YEN,
        "late_available_baseline": _summary(baseline),
        "market_top2_supported": _summary(supported),
        "milestone": _milestone_state(len(supported)),
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
