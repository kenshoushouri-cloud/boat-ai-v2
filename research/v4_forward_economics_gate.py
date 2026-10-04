# -*- coding: utf-8 -*-
"""Pure economics summary for formal V4 prospective evidence.

This module is descriptive only. It does not recommend subscription/plan
changes, alter model thresholds, change stake, create candidates, buy tickets,
or perform any Production/network/database action.
"""
from __future__ import annotations

from datetime import date
from typing import Any

CONTRACT = "v4_forward_economics_evidence_v1"
FORMAL_CORE_RACES_PER_DAY = 6
FORMAL_TICKETS_PER_RACE = 2
FORMAL_TICKET_STAKE_YEN = 100


class V4ForwardEconomicsError(ValueError):
    pass


def _nonnegative_int(value: Any, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise V4ForwardEconomicsError(f"{field} must be a non-negative integer")
    return value


def evaluate_economics(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise V4ForwardEconomicsError("input must be an object")
    if data.get("contract") != CONTRACT:
        raise V4ForwardEconomicsError("unexpected economics contract")

    guards = data.get("policy_guards")
    if not isinstance(guards, dict):
        raise V4ForwardEconomicsError("policy_guards missing")
    required_false = (
        "purchase_action",
        "threshold_changed_for_cost",
        "stake_changed_for_cost",
        "candidate_count_changed_for_cost",
        "result_after_reconstruction",
    )
    for field in required_false:
        if guards.get(field) is not False:
            raise V4ForwardEconomicsError(f"{field} must be false")

    period = data.get("period")
    if not isinstance(period, dict):
        raise V4ForwardEconomicsError("period missing")
    try:
        start = date.fromisoformat(period.get("start_date"))
        end = date.fromisoformat(period.get("end_date"))
    except (TypeError, ValueError) as exc:
        raise V4ForwardEconomicsError("period dates must be ISO dates") from exc
    if end < start:
        raise V4ForwardEconomicsError("period end_date precedes start_date")
    operating_cost = _nonnegative_int(
        period.get("operating_cost_yen"),
        field="operating_cost_yen",
    )
    cost_complete = period.get("operating_cost_complete")
    if not isinstance(cost_complete, bool):
        raise V4ForwardEconomicsError("operating_cost_complete must be boolean")
    cost_components = period.get("cost_components")
    if not isinstance(cost_components, list):
        raise V4ForwardEconomicsError("cost_components must be a list")

    normalized_costs = []
    seen_cost_names: set[str] = set()
    component_total = 0
    for component in cost_components:
        if not isinstance(component, dict):
            raise V4ForwardEconomicsError("cost component must be an object")
        name = component.get("name")
        if not isinstance(name, str) or not name.strip():
            raise V4ForwardEconomicsError("cost component name missing")
        if name in seen_cost_names:
            raise V4ForwardEconomicsError(f"duplicate cost component: {name}")
        seen_cost_names.add(name)
        amount = _nonnegative_int(
            component.get("amount_yen"),
            field=f"cost component {name} amount_yen",
        )
        allocation_note = component.get("allocation_note")
        if not isinstance(allocation_note, str) or not allocation_note.strip():
            raise V4ForwardEconomicsError(
                f"cost component {name} allocation_note missing"
            )
        component_total += amount
        normalized_costs.append(
            {
                "name": name,
                "amount_yen": amount,
                "allocation_note": allocation_note,
            }
        )
    if component_total != operating_cost:
        raise V4ForwardEconomicsError(
            "cost component total does not reconcile to operating_cost_yen"
        )
    if cost_complete and not normalized_costs:
        raise V4ForwardEconomicsError(
            "complete operating cost requires at least one cost component"
        )

    days = data.get("formal_days")
    if not isinstance(days, list) or not days:
        raise V4ForwardEconomicsError("formal_days must be a non-empty list")

    seen_dates: set[str] = set()
    normalized = []
    for row in days:
        if not isinstance(row, dict):
            raise V4ForwardEconomicsError("formal day row must be an object")
        day_text = row.get("date")
        try:
            day = date.fromisoformat(day_text)
        except (TypeError, ValueError) as exc:
            raise V4ForwardEconomicsError("formal day date must be ISO date") from exc
        if day < start or day > end:
            raise V4ForwardEconomicsError(f"formal day outside period: {day_text}")
        if day_text in seen_dates:
            raise V4ForwardEconomicsError(f"duplicate formal day: {day_text}")
        seen_dates.add(day_text)

        races = _nonnegative_int(row.get("core_races"), field=f"{day_text} core_races")
        tickets = _nonnegative_int(row.get("core_tickets"), field=f"{day_text} core_tickets")
        investment = _nonnegative_int(
            row.get("investment_yen"),
            field=f"{day_text} investment_yen",
        )
        gross_return = _nonnegative_int(
            row.get("gross_return_yen"),
            field=f"{day_text} gross_return_yen",
        )
        profit = row.get("profit_yen")
        if not isinstance(profit, int) or isinstance(profit, bool):
            raise V4ForwardEconomicsError(f"{day_text} profit_yen must be an integer")

        if races != FORMAL_CORE_RACES_PER_DAY:
            raise V4ForwardEconomicsError(
                f"{day_text} formal evaluated day must contain exactly 6 core races"
            )
        if tickets != races * FORMAL_TICKETS_PER_RACE:
            raise V4ForwardEconomicsError(
                f"{day_text} formal core must contain exactly two tickets per race"
            )
        expected_investment = tickets * FORMAL_TICKET_STAKE_YEN
        if investment != expected_investment:
            raise V4ForwardEconomicsError(
                f"{day_text} investment must equal 100 JPY per frozen core ticket"
            )
        if profit != gross_return - investment:
            raise V4ForwardEconomicsError(f"{day_text} profit does not reconcile")

        metrics = {}
        for field in (
            "exact_hit_races",
            "head_hit_races",
            "first_second_prefix_hit_races",
            "third_only_miss_races",
        ):
            value = _nonnegative_int(row.get(field), field=f"{day_text} {field}")
            if value > races:
                raise V4ForwardEconomicsError(f"{day_text} {field} exceeds core_races")
            metrics[field] = value

        exact_hits = metrics["exact_hit_races"]
        prefix_hits = metrics["first_second_prefix_hit_races"]
        head_hits = metrics["head_hit_races"]
        third_only = metrics["third_only_miss_races"]
        if not (exact_hits <= prefix_hits <= head_hits):
            raise V4ForwardEconomicsError(
                f"{day_text} hit hierarchy must satisfy exact <= prefix <= head"
            )
        if third_only > prefix_hits - exact_hits:
            raise V4ForwardEconomicsError(
                f"{day_text} third-only misses exceed non-exact prefix hits"
            )

        normalized.append(
            {
                "date": day_text,
                "core_races": races,
                "core_tickets": tickets,
                "investment_yen": investment,
                "gross_return_yen": gross_return,
                "profit_yen": profit,
                **metrics,
            }
        )

    normalized.sort(key=lambda row: row["date"])

    totals = {
        "formal_days": len(normalized),
        "core_races": sum(row["core_races"] for row in normalized),
        "core_tickets": sum(row["core_tickets"] for row in normalized),
        "investment_yen": sum(row["investment_yen"] for row in normalized),
        "gross_return_yen": sum(row["gross_return_yen"] for row in normalized),
        "profit_yen": sum(row["profit_yen"] for row in normalized),
        "exact_hit_races": sum(row["exact_hit_races"] for row in normalized),
        "head_hit_races": sum(row["head_hit_races"] for row in normalized),
        "first_second_prefix_hit_races": sum(
            row["first_second_prefix_hit_races"] for row in normalized
        ),
        "third_only_miss_races": sum(row["third_only_miss_races"] for row in normalized),
    }

    investment = totals["investment_yen"]
    roi = (totals["gross_return_yen"] / investment * 100.0) if investment else 0.0

    cumulative = 0
    peak = 0
    max_drawdown = 0
    for row in normalized:
        cumulative += row["profit_yen"]
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)

    net_after_cost = totals["profit_yen"] - operating_cost

    return {
        "contract": "v4_forward_economics_summary_v1",
        "period": {
            "start_date": period["start_date"],
            "end_date": period["end_date"],
            "operating_cost_yen": operating_cost,
            "operating_cost_complete": cost_complete,
            "cost_components": normalized_costs,
        },
        "formal_days": normalized,
        "summary": {
            **totals,
            "roi_percent": round(roi, 3),
            "max_cumulative_drawdown_yen": max_drawdown,
            "net_after_period_operating_cost_yen": net_after_cost,
            "observed_net_positive": (net_after_cost > 0) if cost_complete else None,
            "net_after_cost_decision_grade": cost_complete,
        },
        "project_milestones_redefined": False,
        "milestone_context_required_separately": True,
        "automatic_plan_change_allowed": False,
        "human_review_required": True,
        "descriptive_only": True,
        "purchase_action": False,
    }
