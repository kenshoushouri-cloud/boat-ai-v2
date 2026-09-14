# -*- coding: utf-8 -*-
"""Pure venue diagnostics for prospective Candidate Discovery V4 evidence.

This module is diagnostic only. It performs no DB/network/Railway/LINE/purchase
action and must not be used to exclude a venue from the current V4/Stage2 V1
study. Any future venue exclusion requires a separately preregistered prospective
experiment after the current global 100-supported-case milestone review.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

V4_FEED_CONTRACT = "candidate_discovery_v4_main_feed_v1"
UNIT_YEN = 100


def _pct(num: float, den: float) -> float | None:
    if den == 0:
        return None
    return round(num / den * 100.0, 3)


def _venue(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw.isdigit():
        raise ValueError("venue_id must be numeric")
    venue = int(raw)
    if venue < 1 or venue > 24:
        raise ValueError("venue_id must be 01..24")
    return f"{venue:02d}"


def _validate_source(row: dict[str, Any]) -> None:
    if str(row.get("source_feed_contract") or "") != V4_FEED_CONTRACT:
        raise ValueError("exact V4 source contract required")
    if row.get("source_prospective_evidence_eligible") is not True:
        raise ValueError("timestamp-proven prospective source required")
    if row.get("counts_as_prospective") is not True:
        raise ValueError("prospective evidence row required")


def _validate_result(row: dict[str, Any]) -> None:
    if row.get("result_ready") is not True:
        return
    hit = bool(row.get("hit"))
    ret = int(row.get("return_yen") or 0)
    if ret < 0:
        raise ValueError("return_yen cannot be negative")
    if hit and ret <= 0:
        raise ValueError("hit must have positive return")
    if not hit and ret != 0:
        raise ValueError("miss must have zero return")


def _normalize_candidates(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
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
        venue_id = _venue(raw.get("venue_id"))
        if len(race_date) != 10 or not race_id:
            raise ValueError("race_date/race_id required")
        if daily_rank not in range(1, 7):
            raise ValueError("daily_rank must be 1..6")
        if core_order not in (1, 2):
            raise ValueError("core_order must be 1 or 2")
        key = (race_date, race_id, core_order)
        if key in seen:
            raise ValueError(f"duplicate candidate identity: {key}")
        seen.add(key)
        _validate_result(raw)
        out.append({
            **raw,
            "race_date": race_date,
            "race_id": race_id,
            "daily_rank": daily_rank,
            "core_order": core_order,
            "venue_id": venue_id,
        })

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in out:
        by_day[row["race_date"]].append(row)
    for day, day_rows in by_day.items():
        if len(day_rows) != 12:
            raise ValueError(f"prospective V4 day must contain 12 core tickets: {day}")
        races = {row["race_id"] for row in day_rows}
        if len(races) != 6:
            raise ValueError(f"prospective V4 day must contain 6 core races: {day}")
        rank_by_race: dict[str, int] = {}
        venue_by_race: dict[str, str] = {}
        orders_by_race: dict[str, set[int]] = defaultdict(set)
        for row in day_rows:
            rid = row["race_id"]
            rank = rank_by_race.setdefault(rid, row["daily_rank"])
            venue = venue_by_race.setdefault(rid, row["venue_id"])
            if rank != row["daily_rank"] or venue != row["venue_id"]:
                raise ValueError(f"race metadata mismatch: {rid}")
            orders_by_race[rid].add(row["core_order"])
        if set(rank_by_race.values()) != {1, 2, 3, 4, 5, 6}:
            raise ValueError(f"daily ranks must be unique 1..6: {day}")
        if any(orders != {1, 2} for orders in orders_by_race.values()):
            raise ValueError(f"each race needs core_order 1 and 2: {day}")
    return sorted(out, key=lambda x: (x["race_date"], x["daily_rank"], x["core_order"]))


def _normalize_stage2(
    rows: Iterable[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    core1 = {
        (row["race_date"], row["race_id"]): row
        for row in candidates
        if row["core_order"] == 1
    }
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("Stage2 row must be an object")
        _validate_source(raw)
        day = str(raw.get("race_date") or "")
        rid = str(raw.get("race_id") or "")
        key = (day, rid)
        if key in seen:
            raise ValueError(f"duplicate Stage2 identity: {key}")
        seen.add(key)
        candidate = core1.get(key)
        if candidate is None:
            raise ValueError(f"Stage2 row has no matching core_order=1 candidate: {key}")
        if int(raw.get("core_order") or 0) != 1:
            raise ValueError("Stage2 V1 venue diagnostics accept core_order=1 only")
        if int(raw.get("daily_rank") or 0) != candidate["daily_rank"]:
            raise ValueError(f"Stage2 daily_rank mismatch: {key}")
        venue_id = _venue(raw.get("venue_id"))
        if venue_id != candidate["venue_id"]:
            raise ValueError(f"Stage2 venue mismatch: {key}")
        late = bool(raw.get("late_snapshot_available"))
        support = bool(raw.get("market_top2_support"))
        if support and not late:
            raise ValueError("market support requires a valid late snapshot")
        _validate_result(raw)
        out.append({
            **raw,
            "race_date": day,
            "race_id": rid,
            "venue_id": venue_id,
            "daily_rank": candidate["daily_rank"],
            "core_order": 1,
            "late_snapshot_available": late,
            "market_top2_support": support,
        })
    if seen != set(core1):
        raise ValueError("Stage2 must contain exactly one row per prospective V4 core race")
    return sorted(out, key=lambda x: (x["race_date"], x["daily_rank"]))


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [row for row in rows if row.get("result_ready") is True]
    hits = sum(1 for row in evaluated if bool(row.get("hit")))
    returns = sum(int(row.get("return_yen") or 0) for row in evaluated)
    investment = len(evaluated) * UNIT_YEN
    hit_returns = sorted(
        (int(row.get("return_yen") or 0) for row in evaluated if bool(row.get("hit"))),
        reverse=True,
    )
    max_hit = hit_returns[0] if hit_returns else 0
    return {
        "evaluated_cases": len(evaluated),
        "evaluated_days": len({row["race_date"] for row in evaluated}),
        "hits": hits,
        "hit_rate_pct": _pct(hits, len(evaluated)),
        "investment_yen": investment,
        "return_yen": returns,
        "profit_yen": returns - investment,
        "roi_pct": _pct(returns, investment),
        "max_single_hit_return_yen": max_hit,
        "max_single_hit_share_of_returns_pct": _pct(max_hit, returns),
    }


def _by_venue(rows: list[dict[str, Any]]) -> dict[str, Any]:
    venues = sorted({row["venue_id"] for row in rows})
    return {venue: _summary([row for row in rows if row["venue_id"] == venue]) for venue in venues}


def summarize_venue_diagnostics(
    candidate_ticket_rows: Iterable[dict[str, Any]],
    stage2_core1_rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    candidates = _normalize_candidates(candidate_ticket_rows)
    stage2 = _normalize_stage2(stage2_core1_rows, candidates)
    supported = [row for row in stage2 if row["market_top2_support"]]
    return {
        "contract": "candidate_discovery_venue_diagnostics_v1",
        "source_feed_contract": V4_FEED_CONTRACT,
        "unit_yen": UNIT_YEN,
        "candidate_all_v4_by_venue": _by_venue(candidates),
        "stage2_supported_core1_by_venue": _by_venue(supported),
        "venue_exclusion_allowed": False,
        "venue_policy": "DIAGNOSTIC_ONLY_NO_EXCLUSION_THROUGH_CURRENT_100_SUPPORTED_CASE_REVIEW",
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
