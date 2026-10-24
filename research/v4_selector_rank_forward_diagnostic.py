# -*- coding: utf-8 -*-
"""Pure Forward diagnostics for Candidate Discovery V4 selector rank.

Research only. This module never selects, removes, reranks, or purchases races.
It summarizes already-frozen formal V4 races after exact same-date outcomes are
settled, keeping the formal two-ticket policy unchanged.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any, Iterable

SOURCE_CONTRACT = "candidate_discovery_v4_main_feed_v1"
UNIT_YEN = 100
FORMAL_POINTS = 2
DAILY_RANKS = {1, 2, 3, 4, 5, 6}
TOP_HALF = {1, 2, 3}
BOTTOM_HALF = {4, 5, 6}


def _norm_ticket(value: Any) -> str:
    text = str(value or "").strip().replace(" ", "").replace("－", "-")
    parts = text.split("-")
    if (
        len(parts) != 3
        or any(not p.isdigit() for p in parts)
        or len(set(parts)) != 3
        or any(int(p) not in range(1, 7) for p in parts)
    ):
        raise ValueError("invalid trifecta ticket")
    return "-".join(str(int(p)) for p in parts)


def _normalize(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("row must be object")
        if str(raw.get("source_feed_contract") or "") != SOURCE_CONTRACT:
            raise ValueError("exact V4 source contract required")
        if raw.get("source_prospective_evidence_eligible") is not True:
            raise ValueError("prospective timing eligibility required")
        if raw.get("purchase_action") is not False:
            raise ValueError("purchase_action must be false")
        if raw.get("result_ready") is not True:
            raise ValueError("only exact-settled rows are accepted")

        day = str(raw.get("race_date") or "")
        rid = str(raw.get("race_id") or "")
        rank = int(raw.get("daily_rank") or 0)
        score = float(raw.get("race_score"))
        if len(day) != 10 or not rid:
            raise ValueError("race_date/race_id required")
        if rank not in DAILY_RANKS:
            raise ValueError("daily_rank must be 1..6")
        if not math.isfinite(score) or score < 0.0 or score > 1.0:
            raise ValueError("race_score must be finite in [0,1]")

        tickets_raw = raw.get("formal_top2")
        if not isinstance(tickets_raw, list) or len(tickets_raw) != FORMAL_POINTS:
            raise ValueError("formal_top2 must contain exactly two tickets")
        tickets = [_norm_ticket(x) for x in tickets_raw]
        if len(set(tickets)) != FORMAL_POINTS:
            raise ValueError("formal_top2 tickets must be distinct")

        actual = _norm_ticket(raw.get("actual_trifecta"))
        payout = int(raw.get("payout_yen") or 0)
        if payout <= 0:
            raise ValueError("official payout_yen must be positive")

        key = (day, rid)
        if key in seen:
            raise ValueError(f"duplicate race identity: {key}")
        seen.add(key)

        out.append(
            {
                "race_date": day,
                "race_id": rid,
                "daily_rank": rank,
                "race_score": score,
                "formal_top2": tickets,
                "actual_trifecta": actual,
                "payout_yen": payout,
            }
        )

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in out:
        by_day[row["race_date"]].append(row)

    for day, day_rows in by_day.items():
        if len(day_rows) != 6:
            raise ValueError(f"exact six formal races required: {day}")
        ranks = {row["daily_rank"] for row in day_rows}
        if ranks != DAILY_RANKS:
            raise ValueError(f"daily ranks must be exactly 1..6: {day}")

    return sorted(out, key=lambda r: (r["race_date"], r["daily_rank"]))


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    investment = len(rows) * FORMAL_POINTS * UNIT_YEN
    returns: list[int] = []
    hits = 0
    for row in rows:
        hit = row["actual_trifecta"] in row["formal_top2"]
        ret = row["payout_yen"] if hit else 0
        returns.append(ret)
        hits += int(hit)

    gross = sum(returns)
    hit_returns = sorted((x for x in returns if x > 0), reverse=True)
    max_hit = hit_returns[0] if hit_returns else 0
    return {
        "races": len(rows),
        "investment_yen": investment,
        "return_yen": gross,
        "profit_yen": gross - investment,
        "roi_percent": round(gross / investment * 100.0, 3) if investment else 0.0,
        "hits": hits,
        "hit_rate_percent": round(hits / len(rows) * 100.0, 3) if rows else 0.0,
        "largest_hit_return_yen": max_hit,
        "largest_hit_share_percent": round(max_hit / gross * 100.0, 3) if gross else 0.0,
        "mean_race_score": round(
            sum(float(row["race_score"]) for row in rows) / len(rows), 6
        ) if rows else 0.0,
    }


def _bootstrap_rank_half(
    rows: list[dict[str, Any]],
    *,
    reps: int,
    seed: int,
) -> dict[str, Any]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_day[row["race_date"]].append(row)
    days = sorted(by_day)
    if not days:
        return {"reps": reps, "seed": seed, "roi_diff_pp_95pct": [0.0, 0.0]}

    daily_pairs: list[tuple[int, int]] = []
    for day in days:
        top = [r for r in by_day[day] if r["daily_rank"] in TOP_HALF]
        bottom = [r for r in by_day[day] if r["daily_rank"] in BOTTOM_HALF]
        daily_pairs.append((_stats(top)["return_yen"], _stats(bottom)["return_yen"]))

    rng = random.Random(seed)
    invest = len(days) * 3 * FORMAL_POINTS * UNIT_YEN
    samples: list[float] = []
    for _ in range(reps):
        top_gross = 0
        bottom_gross = 0
        for _ in days:
            a, b = daily_pairs[rng.randrange(len(daily_pairs))]
            top_gross += a
            bottom_gross += b
        samples.append((top_gross - bottom_gross) / invest * 100.0)

    samples.sort()
    lo = samples[int(0.025 * (len(samples) - 1))]
    hi = samples[int(0.975 * (len(samples) - 1))]
    return {
        "reps": reps,
        "seed": seed,
        "roi_diff_pp_95pct": [round(lo, 3), round(hi, 3)],
        "positive_share_percent": round(
            sum(1 for x in samples if x > 0.0) / len(samples) * 100.0, 3
        ),
    }


def summarize_selector_rank(
    rows: Iterable[dict[str, Any]],
    *,
    bootstrap_reps: int = 20000,
    bootstrap_seed: int = 20260923,
) -> dict[str, Any]:
    normalized = _normalize(rows)
    by_rank = {
        str(rank): _stats([r for r in normalized if r["daily_rank"] == rank])
        for rank in sorted(DAILY_RANKS)
    }
    top = [r for r in normalized if r["daily_rank"] in TOP_HALF]
    bottom = [r for r in normalized if r["daily_rank"] in BOTTOM_HALF]
    top_stats = _stats(top)
    bottom_stats = _stats(bottom)

    return {
        "contract": "v4_selector_rank_forward_diagnostic_v1",
        "source_feed_contract": SOURCE_CONTRACT,
        "formal_points": FORMAL_POINTS,
        "unit_yen": UNIT_YEN,
        "overall": _stats(normalized),
        "by_daily_rank": by_rank,
        "rank_halves": {
            "rank_1_3": top_stats,
            "rank_4_6": bottom_stats,
            "roi_difference_1_3_minus_4_6_pp": round(
                top_stats["roi_percent"] - bottom_stats["roi_percent"], 3
            ),
            "bootstrap": _bootstrap_rank_half(
                normalized, reps=bootstrap_reps, seed=bootstrap_seed
            ),
        },
        "race_score_gate_allowed": False,
        "candidate_count_change_allowed": False,
        "threshold_change_allowed": False,
        "rerank_allowed": False,
        "purchase_action": False,
        "promotion_allowed": False,
        "interpretation": "DIAGNOSTIC_ONLY_NO_SELECTOR_CHANGE",
    }
