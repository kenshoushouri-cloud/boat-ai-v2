# -*- coding: utf-8 -*-
"""Pure V4 point-count marginal revenue evaluator.

This module compares cumulative 1..N ticket strategies only when the ticket
ranking was preserved before race deadlines. Missing pre-result rank evidence is
reported as not evaluable; it is never reconstructed after results.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

CONTRACT = "v4_point_count_marginal_revenue_input_v1"
RESULT_CONTRACT = "v4_point_count_marginal_revenue_result_v1"
EXPECTED_RACES_PER_DAY = 6
EXPECTED_STAKE_YEN = 100
MAX_SUPPORTED_POINTS = 5


class V4PointCountMarginalRevenueError(ValueError):
    pass


def _aware_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise V4PointCountMarginalRevenueError(
            f"{field} must be an ISO datetime string"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise V4PointCountMarginalRevenueError(
            f"{field} is not valid ISO datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise V4PointCountMarginalRevenueError(
            f"{field} must be timezone-aware"
        )
    return parsed


def _ticket(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise V4PointCountMarginalRevenueError(f"{field} must be a string")
    parts = value.split("-")
    if (
        len(parts) != 3
        or any(not part.isdigit() for part in parts)
        or len(set(parts)) != 3
        or any(not (1 <= int(part) <= 6) for part in parts)
    ):
        raise V4PointCountMarginalRevenueError(
            f"{field} must be a valid trifecta ticket"
        )
    return value


def _max_drawdown(profits: list[int]) -> int:
    running = 0
    peak = 0
    max_drawdown = 0
    for profit in profits:
        running += profit
        peak = max(peak, running)
        max_drawdown = max(max_drawdown, peak - running)
    return max_drawdown


def evaluate_point_counts(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("contract") != CONTRACT:
        raise V4PointCountMarginalRevenueError("unexpected input contract")

    stake = data.get("stake_per_ticket_yen")
    if stake != EXPECTED_STAKE_YEN:
        raise V4PointCountMarginalRevenueError(
            "stake_per_ticket_yen must remain fixed at 100"
        )

    max_requested = data.get("max_requested_points")
    if (
        not isinstance(max_requested, int)
        or isinstance(max_requested, bool)
        or not (1 <= max_requested <= MAX_SUPPORTED_POINTS)
    ):
        raise V4PointCountMarginalRevenueError(
            "max_requested_points must be an integer from 1 to 5"
        )

    days = data.get("days")
    if not isinstance(days, list) or not days:
        raise V4PointCountMarginalRevenueError("days must be a non-empty list")

    normalized_races: list[dict[str, Any]] = []
    available_rank_count = MAX_SUPPORTED_POINTS
    seen_dates: set[str] = set()

    for day in days:
        if not isinstance(day, dict):
            raise V4PointCountMarginalRevenueError("day must be an object")
        target_date = day.get("target_date")
        if not isinstance(target_date, str) or target_date in seen_dates:
            raise V4PointCountMarginalRevenueError(
                "target_date missing or duplicated"
            )
        seen_dates.add(target_date)

        generated = _aware_datetime(
            day.get("ranking_evidence_generated_at"),
            field=f"{target_date} ranking_evidence_generated_at",
        )
        digest = day.get("ranking_evidence_sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise V4PointCountMarginalRevenueError(
                f"{target_date} ranking_evidence_sha256 must be lowercase 64-hex"
            )

        ranking_count = day.get("ranking_count")
        if (
            not isinstance(ranking_count, int)
            or isinstance(ranking_count, bool)
            or not (1 <= ranking_count <= MAX_SUPPORTED_POINTS)
        ):
            raise V4PointCountMarginalRevenueError(
                f"{target_date} ranking_count must be 1..5"
            )
        available_rank_count = min(available_rank_count, ranking_count)

        races = day.get("races")
        if not isinstance(races, list) or len(races) != EXPECTED_RACES_PER_DAY:
            raise V4PointCountMarginalRevenueError(
                f"{target_date} must contain exactly 6 formal races"
            )

        ranks = sorted(race.get("daily_rank") for race in races if isinstance(race, dict))
        if ranks != [1, 2, 3, 4, 5, 6]:
            raise V4PointCountMarginalRevenueError(
                f"{target_date} daily_rank must be exactly 1..6"
            )

        for race in races:
            race_id = race.get("race_id")
            if not isinstance(race_id, str) or not race_id.startswith(
                target_date.replace("-", "") + "_"
            ):
                raise V4PointCountMarginalRevenueError(
                    f"{target_date} race_id mismatch"
                )
            deadline = _aware_datetime(
                race.get("deadline_at"),
                field=f"{race_id} deadline_at",
            )
            if generated >= deadline:
                raise V4PointCountMarginalRevenueError(
                    f"{race_id} ranking evidence is not pre-deadline"
                )

            ranked = race.get("ranked_tickets")
            if not isinstance(ranked, list) or len(ranked) != ranking_count:
                raise V4PointCountMarginalRevenueError(
                    f"{race_id} ranked_tickets must exactly match ranking_count"
                )
            normalized_tickets = [
                _ticket(ticket, field=f"{race_id} ranked ticket")
                for ticket in ranked
            ]
            if len(set(normalized_tickets)) != len(normalized_tickets):
                raise V4PointCountMarginalRevenueError(
                    f"{race_id} ranked_tickets must be unique"
                )

            actual = _ticket(
                race.get("actual_trifecta"),
                field=f"{race_id} actual_trifecta",
            )
            payout = race.get("trifecta_payout_yen")
            if (
                not isinstance(payout, int)
                or isinstance(payout, bool)
                or payout < 0
            ):
                raise V4PointCountMarginalRevenueError(
                    f"{race_id} trifecta_payout_yen must be nonnegative integer"
                )

            normalized_races.append(
                {
                    "target_date": target_date,
                    "race_id": race_id,
                    "deadline_at": deadline,
                    "daily_rank": race["daily_rank"],
                    "ranked_tickets": normalized_tickets,
                    "actual_trifecta": actual,
                    "trifecta_payout_yen": payout,
                }
            )

    normalized_races.sort(
        key=lambda race: (
            race["deadline_at"],
            race["race_id"],
        )
    )
    race_count = len(normalized_races)

    strategies: list[dict[str, Any]] = []
    previous_gross = 0
    previous_hits = 0

    for points in range(1, max_requested + 1):
        if points > available_rank_count:
            strategies.append(
                {
                    "points_per_race": points,
                    "status": "NOT_EVALUABLE_MISSING_PRE_RESULT_RANKS",
                    "required_rank_count": points,
                    "available_rank_count": available_rank_count,
                    "post_result_reconstruction_allowed": False,
                }
            )
            continue

        gross = 0
        hits = 0
        per_race_profits: list[int] = []
        per_day: dict[str, dict[str, int]] = {}
        for race in normalized_races:
            selected = race["ranked_tickets"][:points]
            hit = race["actual_trifecta"] in selected
            return_yen = race["trifecta_payout_yen"] if hit else 0
            investment = stake * points
            profit = return_yen - investment
            gross += return_yen
            hits += int(hit)
            per_race_profits.append(profit)

            day = per_day.setdefault(
                race["target_date"],
                {"investment_yen": 0, "gross_return_yen": 0, "profit_yen": 0},
            )
            day["investment_yen"] += investment
            day["gross_return_yen"] += return_yen
            day["profit_yen"] += profit

        investment = race_count * stake * points
        profit = gross - investment
        incremental_investment = race_count * stake
        incremental_gross = gross - previous_gross
        incremental_profit = incremental_gross - incremental_investment
        incremental_hits = hits - previous_hits

        strategies.append(
            {
                "points_per_race": points,
                "status": "EVALUATED",
                "race_count": race_count,
                "investment_yen": investment,
                "gross_return_yen": gross,
                "profit_yen": profit,
                "roi_percent": round(gross / investment * 100.0, 3),
                "hit_races": hits,
                "hit_rate_percent": round(hits / race_count * 100.0, 3),
                "max_drawdown_yen": _max_drawdown(per_race_profits),
                "incremental_point": {
                    "point_rank": points,
                    "incremental_investment_yen": incremental_investment,
                    "incremental_gross_return_yen": incremental_gross,
                    "incremental_profit_yen": incremental_profit,
                    "marginal_roi_percent": round(
                        incremental_gross / incremental_investment * 100.0,
                        3,
                    ),
                    "incremental_hit_races": incremental_hits,
                    "incremental_hit_rate_percent": round(
                        incremental_hits / race_count * 100.0,
                        3,
                    ),
                },
                "day_summaries": [
                    {
                        "target_date": target_date,
                        **summary,
                    }
                    for target_date, summary in sorted(per_day.items())
                ],
            }
        )
        previous_gross = gross
        previous_hits = hits

    return {
        "contract": RESULT_CONTRACT,
        "formal_days": len(days),
        "formal_races": race_count,
        "stake_per_ticket_yen": stake,
        "requested_point_range": [1, max_requested],
        "available_pre_result_rank_count": available_rank_count,
        "strategies": strategies,
        "historical_3_to_5_reconstruction_performed": False,
        "purchase_action": False,
        "production_mutation": False,
    }
