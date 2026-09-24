# -*- coding: utf-8 -*-
"""Preregistered contract for a low-freedom V4 daily race-count walk-forward.

The experiment keeps the current V4 daily race ordering and current formal
2-ticket ordering. It changes only how many of the six daily races are actually
included: top 1, top 2, or top 3 by frozen daily_race_rank.

The daily count used in an evaluation block is chosen from strictly earlier
chronological blocks. No odds, market rank, venue, race number, date filter,
structural reranker, ticket reranker, stake sizing, or current-block result can
influence the selected count.
"""
from __future__ import annotations

from statistics import median
from typing import Any, Iterable, Mapping

RACE_COUNT_CANDIDATES = (1, 2, 3)
CURRENT_CONTROL_RACES = 6
POINTS_PER_RACE = 2
UNIT_YEN = 100
BLOCK_COUNT = 10
WARMUP_BLOCKS = 2
WARMUP_RACE_COUNT = 3

SELECTION_METRIC = (
    "max_median_prior_block_roi_then_median_positive_day_rate_"
    "then_cumulative_roi_then_cumulative_positive_day_rate_then_smaller_count"
)


def _daily_rows(rows: Iterable[Mapping[str, Any]], race_count: int) -> list[dict[str, Any]]:
    if race_count not in RACE_COUNT_CANDIDATES:
        raise ValueError("race_count must be one of 1,2,3")

    by_date: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        day = str(row["date"])
        by_date.setdefault(day, []).append(row)

    selected: list[dict[str, Any]] = []
    for day in sorted(by_date):
        day_rows = sorted(
            by_date[day],
            key=lambda row: (int(row["daily_rank"]), str(row["race_id"])),
        )
        if len(day_rows) != CURRENT_CONTROL_RACES:
            raise ValueError(f"{day} must contain exact six frozen V4 races")
        ranks = [int(row["daily_rank"]) for row in day_rows]
        if ranks != list(range(1, CURRENT_CONTROL_RACES + 1)):
            raise ValueError(f"{day} daily ranks must be exactly 1..6")
        selected.extend(dict(row) for row in day_rows[:race_count])
    return selected


def ticket_return_yen(row: Mapping[str, Any]) -> int:
    ranked = list(row["ranked_top5"])
    if len(ranked) != 5 or len(set(ranked)) != 5:
        raise ValueError("ranked_top5 must contain five unique tickets")
    payout = int(row["payout_yen"])
    if payout <= 0:
        raise ValueError("payout_yen must be positive")
    actual = str(row["actual_trifecta"])
    return payout if actual in set(ranked[:POINTS_PER_RACE]) else 0


def block_metrics(
    rows: Iterable[Mapping[str, Any]],
    *,
    race_count: int,
) -> dict[str, float]:
    selected = _daily_rows(rows, race_count)
    if not selected:
        raise ValueError("block has no selected races")

    by_date: dict[str, list[Mapping[str, Any]]] = {}
    for row in selected:
        by_date.setdefault(str(row["date"]), []).append(row)

    gross = sum(ticket_return_yen(row) for row in selected)
    investment = len(selected) * POINTS_PER_RACE * UNIT_YEN

    positive_days = 0
    for day_rows in by_date.values():
        day_gross = sum(ticket_return_yen(row) for row in day_rows)
        day_investment = len(day_rows) * POINTS_PER_RACE * UNIT_YEN
        positive_days += int(day_gross > day_investment)

    return {
        "roi_percent": gross / investment * 100.0,
        "positive_day_rate_percent": positive_days / len(by_date) * 100.0,
        "profit_yen": float(gross - investment),
        "days": float(len(by_date)),
    }


def race_count_training_score(
    rows: Iterable[Mapping[str, Any]],
    *,
    race_count: int,
    current_block: int,
) -> tuple[float, float, float, float, int]:
    if race_count not in RACE_COUNT_CANDIDATES:
        raise ValueError("race_count must be one of 1,2,3")
    if not (1 <= current_block <= BLOCK_COUNT):
        raise ValueError("current_block outside frozen block range")

    prior = [row for row in rows if int(row["block"]) < current_block]
    if not prior:
        raise ValueError("no prior rows")

    by_block: dict[int, list[Mapping[str, Any]]] = {}
    for row in prior:
        by_block.setdefault(int(row["block"]), []).append(row)

    block_stats = [
        block_metrics(by_block[block], race_count=race_count)
        for block in sorted(by_block)
    ]

    median_roi = float(median(stat["roi_percent"] for stat in block_stats))
    median_positive = float(
        median(stat["positive_day_rate_percent"] for stat in block_stats)
    )

    cumulative = block_metrics(prior, race_count=race_count)

    return (
        median_roi,
        median_positive,
        float(cumulative["roi_percent"]),
        float(cumulative["positive_day_rate_percent"]),
        -race_count,
    )


def choose_race_count_for_block(
    rows: Iterable[Mapping[str, Any]],
    *,
    current_block: int,
) -> int:
    rows = list(rows)
    if not (1 <= current_block <= BLOCK_COUNT):
        raise ValueError("current_block outside frozen block range")
    if current_block <= WARMUP_BLOCKS:
        return WARMUP_RACE_COUNT

    scores = {
        race_count: race_count_training_score(
            rows,
            race_count=race_count,
            current_block=current_block,
        )
        for race_count in RACE_COUNT_CANDIDATES
    }
    return max(RACE_COUNT_CANDIDATES, key=lambda count: scores[count])


def contract_metadata() -> dict[str, Any]:
    return {
        "contract": "v4_daily_1to3_race_count_v1",
        "race_count_candidates": list(RACE_COUNT_CANDIDATES),
        "current_control_races": CURRENT_CONTROL_RACES,
        "points_per_race": POINTS_PER_RACE,
        "unit_yen": UNIT_YEN,
        "block_count": BLOCK_COUNT,
        "warmup_blocks": WARMUP_BLOCKS,
        "warmup_race_count": WARMUP_RACE_COUNT,
        "selection_metric": SELECTION_METRIC,
        "race_order_source": "frozen_daily_race_rank",
        "ticket_order_source": "frozen_ranked_top5_ranks_1_2",
        "zero_race_day_allowed": False,
        "more_than_three_races_allowed": False,
        "ticket_rerank_allowed": False,
        "market_input_allowed": False,
        "odds_gate_allowed": False,
        "venue_filter_allowed": False,
        "race_number_filter_allowed": False,
        "date_filter_allowed": False,
        "stake_change_allowed": False,
        "production_change_allowed": False,
        "purchase_action": False,
    }
