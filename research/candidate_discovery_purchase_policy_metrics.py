# -*- coding: utf-8 -*-
"""Pure preregistered metrics for Candidate Discovery V4 purchase-policy research.

This module performs no DB/network/Railway/LINE/purchase action. It consumes
already-frozen prospective V4 ticket rows plus frozen Stage-2 annotation rows.
The Stage-2 V1 contract is intentionally limited to core_order=1.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

V4_FEED_CONTRACT = "candidate_discovery_v4_main_feed_v1"
UNIT_YEN = 100
MILESTONES = (30, 50, 100)
RANK_BUCKETS = {
    "rank_1_2": {1, 2},
    "rank_3_4": {3, 4},
    "rank_5_6": {5, 6},
}


def _pct(num: float, den: float) -> float | None:
    if den == 0:
        return None
    return round(num / den * 100.0, 3)


def _validate_source(row: dict[str, Any]) -> None:
    if str(row.get("source_feed_contract") or "") != V4_FEED_CONTRACT:
        raise ValueError("exact V4 source contract required")
    if row.get("source_prospective_evidence_eligible") is not True:
        raise ValueError("timestamp-proven prospective source required")
    if row.get("counts_as_prospective") is not True:
        raise ValueError("row must count as prospective evidence")


def _validate_result(row: dict[str, Any]) -> None:
    if row.get("result_ready") is not True:
        return
    ret = int(row.get("return_yen") or 0)
    if ret < 0:
        raise ValueError("return_yen cannot be negative")
    hit = bool(row.get("hit"))
    if hit and ret <= 0:
        raise ValueError("hit must have positive return")
    if not hit and ret != 0:
        raise ValueError("miss must have zero return")


def _normalized_candidate_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("candidate row must be an object")
        _validate_source(raw)
        race_date = str(raw.get("race_date") or "")
        race_id = str(raw.get("race_id") or "")
        daily_rank = int(raw.get("daily_rank") or 0)
        core_order = int(raw.get("core_order") or 0)
        if len(race_date) != 10 or not race_id:
            raise ValueError("candidate race_date/race_id required")
        if daily_rank not in range(1, 7):
            raise ValueError("candidate daily_rank must be 1..6")
        if core_order not in (1, 2):
            raise ValueError("candidate core_order must be 1 or 2")
        key = (race_date, race_id, core_order)
        if key in seen:
            raise ValueError(f"duplicate candidate ticket identity: {key}")
        seen.add(key)
        _validate_result(raw)
        out.append({
            **raw,
            "race_date": race_date,
            "race_id": race_id,
            "daily_rank": daily_rank,
            "core_order": core_order,
        })

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in out:
        by_day[row["race_date"]].append(row)
    for race_date, day_rows in by_day.items():
        if len(day_rows) != 12:
            raise ValueError(f"candidate day must contain exactly 12 tickets: {race_date}")
        race_ids = {row["race_id"] for row in day_rows}
        if len(race_ids) != 6:
            raise ValueError(f"candidate day must contain exactly 6 races: {race_date}")
        ranks_by_race: dict[str, int] = {}
        orders_by_race: dict[str, set[int]] = defaultdict(set)
        for row in day_rows:
            rid = row["race_id"]
            prior = ranks_by_race.setdefault(rid, row["daily_rank"])
            if prior != row["daily_rank"]:
                raise ValueError(f"daily_rank mismatch within race: {rid}")
            orders_by_race[rid].add(row["core_order"])
        if set(ranks_by_race.values()) != {1, 2, 3, 4, 5, 6}:
            raise ValueError(f"candidate day must contain unique daily ranks 1..6: {race_date}")
        if any(orders != {1, 2} for orders in orders_by_race.values()):
            raise ValueError(f"each core race must contain core_order 1 and 2: {race_date}")
    return sorted(out, key=lambda x: (x["race_date"], x["daily_rank"], x["core_order"], x["race_id"]))


def _normalized_stage2_rows(
    rows: Iterable[dict[str, Any]], candidate_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    candidate_core1 = {
        (row["race_date"], row["race_id"]): row
        for row in candidate_rows
        if row["core_order"] == 1
    }
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("stage2 row must be an object")
        _validate_source(raw)
        race_date = str(raw.get("race_date") or "")
        race_id = str(raw.get("race_id") or "")
        daily_rank = int(raw.get("daily_rank") or 0)
        core_order = int(raw.get("core_order") or 0)
        if core_order != 1:
            raise ValueError("frozen Stage2 V1 accepts core_order=1 only")
        key = (race_date, race_id)
        if key in seen:
            raise ValueError(f"duplicate Stage2 race identity: {key}")
        seen.add(key)
        candidate = candidate_core1.get(key)
        if candidate is None:
            raise ValueError(f"Stage2 row has no matching prospective core_order=1 candidate: {key}")
        if daily_rank != candidate["daily_rank"]:
            raise ValueError(f"Stage2 daily_rank mismatch: {key}")
        late = bool(raw.get("late_snapshot_available"))
        support = bool(raw.get("market_top2_support"))
        if support and not late:
            raise ValueError("market support requires a valid late snapshot")
        _validate_result(raw)
        out.append({
            **raw,
            "race_date": race_date,
            "race_id": race_id,
            "daily_rank": daily_rank,
            "core_order": 1,
            "late_snapshot_available": late,
            "market_top2_support": support,
        })

    candidate_keys = set(candidate_core1)
    if seen != candidate_keys:
        missing = sorted(candidate_keys - seen)
        extra = sorted(seen - candidate_keys)
        raise ValueError(f"Stage2 must contain exactly one row per V4 core race missing={missing} extra={extra}")
    return sorted(out, key=lambda x: (x["race_date"], x["daily_rank"], x["race_id"]))


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [row for row in rows if row.get("result_ready") is True]
    hits = 0
    returns = 0
    losing = 0
    max_losing = 0
    equity = 0
    peak = 0
    max_drawdown = 0
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hit_returns: list[int] = []

    for row in evaluated:
        hit = bool(row.get("hit"))
        ret = int(row.get("return_yen") or 0)
        if hit:
            hits += 1
            losing = 0
            hit_returns.append(ret)
        else:
            losing += 1
            max_losing = max(max_losing, losing)
        returns += ret
        equity += ret - UNIT_YEN
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        by_day[row["race_date"]].append(row)

    investment = len(evaluated) * UNIT_YEN
    positive_days = 0
    for day_rows in by_day.values():
        day_return = sum(int(row.get("return_yen") or 0) for row in day_rows)
        if day_return > len(day_rows) * UNIT_YEN:
            positive_days += 1
    max_hit = max(hit_returns) if hit_returns else 0
    return {
        "evaluated_cases": len(evaluated),
        "evaluated_days": len(by_day),
        "hits": hits,
        "hit_rate_pct": _pct(hits, len(evaluated)),
        "investment_yen": investment,
        "return_yen": returns,
        "profit_yen": returns - investment,
        "roi_pct": _pct(returns, investment),
        "max_losing_ticket_streak": max_losing,
        "max_drawdown_yen": max_drawdown,
        "positive_days": positive_days,
        "positive_day_rate_pct": _pct(positive_days, len(by_day)),
        "max_single_hit_return_yen": max_hit,
        "max_single_hit_share_of_returns_pct": _pct(max_hit, returns),
    }


def _bucketed(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        name: _summary([row for row in rows if row["daily_rank"] in ranks])
        for name, ranks in RANK_BUCKETS.items()
    }


def _milestone(n: int) -> dict[str, Any]:
    reached = [value for value in MILESTONES if n >= value]
    next_target = next((value for value in MILESTONES if n < value), None)
    return {
        "supported_evaluated_cases": n,
        "reached": reached,
        "next_target": next_target,
        "remaining_to_next": (next_target - n) if next_target is not None else 0,
        "promotion_allowed": False,
    }


def summarize_purchase_policy(
    candidate_ticket_rows: Iterable[dict[str, Any]],
    stage2_core1_rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize the preregistered V4 candidate/purchase-policy views.

    Candidate rows must contain all 12 Stage-1 core tickets for every included
    successful prospective day. Stage2 rows must contain exactly one core_order=1
    row per core race, whether or not a late snapshot/support exists.
    """
    candidates = _normalized_candidate_rows(candidate_ticket_rows)
    stage2 = _normalized_stage2_rows(stage2_core1_rows, candidates)

    candidate_dates = sorted({row["race_date"] for row in candidates})
    stage2_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in stage2:
        stage2_by_day[row["race_date"]].append(row)

    days_with_late = sum(
        1 for day in candidate_dates
        if any(row["late_snapshot_available"] for row in stage2_by_day[day])
    )
    supported_days = sum(
        1 for day in candidate_dates
        if any(row["market_top2_support"] for row in stage2_by_day[day])
    )
    zero_supported_days = len(candidate_dates) - supported_days
    late_rows = [row for row in stage2 if row["late_snapshot_available"]]
    supported_rows = [row for row in stage2 if row["market_top2_support"]]
    supported_evaluated = [row for row in supported_rows if row.get("result_ready") is True]

    return {
        "contract": "candidate_discovery_purchase_policy_metrics_v1",
        "source_feed_contract": V4_FEED_CONTRACT,
        "unit_yen": UNIT_YEN,
        "candidate_feed": {
            "prospective_days": len(candidate_dates),
            "core_races": len(candidates) // 2,
            "core_tickets": len(candidates),
            "avg_core_tickets_per_day": round(len(candidates) / len(candidate_dates), 3) if candidate_dates else None,
            "all_v4": _summary(candidates),
            "by_race_rank": _bucketed(candidates),
            "by_core_order": {
                "core_order_1": _summary([row for row in candidates if row["core_order"] == 1]),
                "core_order_2": _summary([row for row in candidates if row["core_order"] == 2]),
            },
        },
        "stage2_v1": {
            "core_order": 1,
            "prospective_days": len(candidate_dates),
            "annotated_core1_cases": len(stage2),
            "late_snapshot_available_cases": len(late_rows),
            "days_with_late_snapshot": days_with_late,
            "supported_cases": len(supported_rows),
            "supported_days": supported_days,
            "zero_supported_days": zero_supported_days,
            "zero_supported_day_rate_pct": _pct(zero_supported_days, len(candidate_dates)),
            "avg_supported_cases_per_day": round(len(supported_rows) / len(candidate_dates), 3) if candidate_dates else None,
            "supported_performance": _summary(supported_rows),
            "supported_by_race_rank": _bucketed(supported_rows),
            "milestone": _milestone(len(supported_evaluated)),
        },
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
