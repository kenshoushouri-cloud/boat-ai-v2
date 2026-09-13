# -*- coding: utf-8 -*-
"""Pure stability metrics for exact Candidate Discovery frozen evaluations.

Input is one or more outputs from candidate_discovery_frozen_eval_pg.py.
This module performs no database/network access and changes no candidate rule.
It keeps V1/V2 baseline core, true V4 core, legacy carryover, and total feed
separate so baseline evidence can never be mislabeled as V4 Forward evidence.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

UNIT_YEN = 100
BASELINE_SOURCE_CONTRACT = "candidate_discovery_main_feed_v1"
V4_SOURCE_CONTRACT = "candidate_discovery_v4_main_feed_v1"
ALLOWED_SOURCE_CONTRACTS = {BASELINE_SOURCE_CONTRACT, V4_SOURCE_CONTRACT}


def _round_pct(num: float, den: float) -> float | None:
    if den == 0:
        return None
    return round(num / den * 100.0, 3)


def _segment(tier: str, source_contract: str) -> str:
    if str(tier).strip().upper() in {"L", "LEGACY"}:
        return "legacy"
    if source_contract == BASELINE_SOURCE_CONTRACT:
        return "baseline_core"
    if source_contract == V4_SOURCE_CONTRACT:
        return "v4_core"
    raise ValueError(f"unexpected source contract: {source_contract}")


def _normalize_documents(documents: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    missing = 0

    for doc in documents:
        if not isinstance(doc, dict):
            raise ValueError("evaluation document must be an object")
        if doc.get("contract") != "candidate_discovery_frozen_forward_eval_v1":
            raise ValueError("unexpected frozen evaluation contract")
        if doc.get("mutation_performed") is not False:
            raise ValueError("evaluation document reports mutation")
        if doc.get("line_sent") is not False or doc.get("purchase_action") is not False:
            raise ValueError("evaluation document violates fail-closed flags")
        if doc.get("production_behavior_changed") is not False:
            raise ValueError("evaluation document reports Production behavior change")

        source_contract = str(doc.get("source_contract") or "")
        if source_contract not in ALLOWED_SOURCE_CONTRACTS:
            raise ValueError(f"unexpected source contract: {source_contract}")
        source_date = str(doc.get("source_date") or "")
        for raw in doc.get("rows") or []:
            race_id = str(raw.get("race_id") or "")
            if not race_id:
                raise ValueError("race_id is required")
            if race_id in seen:
                raise ValueError(f"duplicate race_id: {race_id}")
            seen.add(race_id)

            status = str(raw.get("status") or "")
            if status != "EVALUATED":
                missing += 1
                continue

            tickets = [str(x) for x in raw.get("tickets") or [] if str(x)]
            if not tickets:
                raise ValueError(f"evaluated row has no tickets: {race_id}")
            investment = int(raw.get("investment_yen") or 0)
            expected_investment = len(tickets) * UNIT_YEN
            if investment != expected_investment:
                raise ValueError(
                    f"flat-stake mismatch for {race_id}: investment={investment} expected={expected_investment}"
                )
            hit = bool(raw.get("hit"))
            returns = int(raw.get("return_yen") or 0)
            if returns < 0:
                raise ValueError(f"negative return: {race_id}")
            if hit and returns <= 0:
                raise ValueError(f"hit with non-positive return: {race_id}")
            if not hit and returns != 0:
                raise ValueError(f"miss with nonzero return: {race_id}")

            date = source_date
            if not date and len(race_id) >= 8 and race_id[:8].isdigit():
                date = f"{race_id[:4]}-{race_id[4:6]}-{race_id[6:8]}"
            if len(date) != 10:
                raise ValueError(f"source date missing for {race_id}")

            tier = str(raw.get("tier") or "?")
            rows.append({
                "date": date,
                "month": date[:7],
                "race_id": race_id,
                "tier": tier,
                "source_contract": source_contract,
                "segment": _segment(tier, source_contract),
                "ticket_count": len(tickets),
                "hit": hit,
                "investment_yen": investment,
                "return_yen": returns,
                "profit_yen": returns - investment,
            })

    rows.sort(key=lambda x: (x["date"], x["race_id"]))
    return rows, missing


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = len(rows)
    dates = sorted({row["date"] for row in rows})
    tickets = sum(int(row["ticket_count"]) for row in rows)
    hits = sum(1 for row in rows if row["hit"])
    investment = sum(int(row["investment_yen"]) for row in rows)
    returns = sum(int(row["return_yen"]) for row in rows)
    profit = returns - investment

    max_losing = 0
    current_losing = 0
    equity = 0
    peak = 0
    max_drawdown = 0
    hit_returns: list[int] = []
    for row in rows:
        if row["hit"]:
            current_losing = 0
            hit_returns.append(int(row["return_yen"]))
        else:
            current_losing += 1
            max_losing = max(max_losing, current_losing)
        equity += int(row["profit_yen"])
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    day_profit: dict[str, int] = defaultdict(int)
    month_profit: dict[str, int] = defaultdict(int)
    month_investment: dict[str, int] = defaultdict(int)
    month_return: dict[str, int] = defaultdict(int)
    for row in rows:
        day_profit[row["date"]] += int(row["profit_yen"])
        month_profit[row["month"]] += int(row["profit_yen"])
        month_investment[row["month"]] += int(row["investment_yen"])
        month_return[row["month"]] += int(row["return_yen"])

    positive_days = sum(1 for value in day_profit.values() if value > 0)
    positive_months = sum(1 for value in month_profit.values() if value > 0)
    monthly = {
        month: {
            "investment_yen": month_investment[month],
            "return_yen": month_return[month],
            "profit_yen": month_profit[month],
            "roi_pct": _round_pct(month_return[month], month_investment[month]),
        }
        for month in sorted(month_profit)
    }

    hit_returns.sort(reverse=True)
    max_single = hit_returns[0] if hit_returns else 0
    top3 = sum(hit_returns[:3])

    return {
        "evaluated_races": evaluated,
        "evaluation_days": len(dates),
        "tickets": tickets,
        "avg_tickets_per_day": round(tickets / len(dates), 3) if dates else None,
        "hits": hits,
        "race_hit_rate_pct": _round_pct(hits, evaluated),
        "investment_yen": investment,
        "return_yen": returns,
        "profit_yen": profit,
        "roi_pct": _round_pct(returns, investment),
        "max_losing_race_streak": max_losing,
        "max_drawdown_yen": max_drawdown,
        "positive_days": positive_days,
        "positive_day_rate_pct": _round_pct(positive_days, len(dates)),
        "positive_months": positive_months,
        "months": len(monthly),
        "positive_month_rate_pct": _round_pct(positive_months, len(monthly)),
        "max_single_hit_return_yen": max_single,
        "max_single_hit_share_of_returns_pct": _round_pct(max_single, returns),
        "top3_hit_share_of_returns_pct": _round_pct(top3, returns),
        "monthly": monthly,
    }


def summarize_frozen_forward(documents: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows, missing = _normalize_documents(documents)
    baseline_core = [row for row in rows if row["segment"] == "baseline_core"]
    v4_core = [row for row in rows if row["segment"] == "v4_core"]
    legacy = [row for row in rows if row["segment"] == "legacy"]
    baseline_source = [row for row in rows if row["source_contract"] == BASELINE_SOURCE_CONTRACT]
    v4_source = [row for row in rows if row["source_contract"] == V4_SOURCE_CONTRACT]
    return {
        "contract": "candidate_discovery_forward_stability_metrics_v1",
        "all_feed": _summary(rows),
        "baseline_source": _summary(baseline_source),
        "v4_source": _summary(v4_source),
        "baseline_core": _summary(baseline_core),
        "v4_core": _summary(v4_core),
        "legacy_carryover": _summary(legacy),
        "source_contracts_seen": sorted({row["source_contract"] for row in rows}),
        "missing_result_rows": missing,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
