# -*- coding: utf-8 -*-
"""Preregistered V4 selector for exactly one race per evaluable day.

The selector starts from the same six V4 races already frozen before results.
It keeps the current formal two tickets and 100-yen stake per ticket.

Selection uses no odds, EV, market rank, venue, race number, calendar filter,
ticket reranking, or same-day result feedback.

Only one broad pre-result Top5 structural context is learned economically from
strictly earlier chronological blocks. Within an equally scored context, the
already-frozen V4 race_score and daily_race_rank are conservative tie-breakers.
"""
from __future__ import annotations

from statistics import median
from typing import Any, Iterable, Mapping, Sequence

CONTEXTS = ("H1_P0", "H1_P1", "HM_P0", "HM_P1")
DAILY_CANDIDATES = 6
SELECTED_RACES_PER_DAY = 1
POINTS_PER_RACE = 2
UNIT_YEN = 100
BLOCK_COUNT = 10
WARMUP_BLOCKS = 2
MIN_CONTEXT_RACES_PER_BLOCK = 10
MIN_PRIOR_QUALIFYING_BLOCKS = 2

SELECTION_METRIC = (
    "context_median_prior_block_roi_then_context_cumulative_roi_"
    "then_current_race_score_then_lower_daily_rank"
)


def _ticket_parts(ticket: str) -> tuple[str, str, str]:
    parts = str(ticket).split("-")
    if len(parts) != 3 or len(set(parts)) != 3:
        raise ValueError(f"invalid trifecta ticket: {ticket}")
    return parts[0], parts[1], parts[2]


def structural_context(ranked_top5: Sequence[str]) -> str:
    if len(ranked_top5) != 5 or len(set(ranked_top5)) != 5:
        raise ValueError("ranked_top5 must contain five unique frozen tickets")
    parsed = [_ticket_parts(ticket) for ticket in ranked_top5]
    head_bucket = "H1" if len({parts[0] for parts in parsed[:3]}) == 1 else "HM"
    prefix_bucket = "P1" if parsed[0][:2] == parsed[1][:2] else "P0"
    return f"{head_bucket}_{prefix_bucket}"


def formal_two_return_yen(row: Mapping[str, Any]) -> int:
    ranked = list(row["ranked_top5"])
    if len(ranked) != 5 or len(set(ranked)) != 5:
        raise ValueError("ranked_top5 must contain five unique frozen tickets")
    payout = int(row["payout_yen"])
    if payout <= 0:
        raise ValueError("payout_yen must be positive")
    actual = str(row["actual_trifecta"])
    return payout if actual in set(ranked[:POINTS_PER_RACE]) else 0


def qualifying_context_blocks(
    rows: Iterable[Mapping[str, Any]],
    *,
    context: str,
    current_block: int,
) -> dict[int, list[Mapping[str, Any]]]:
    if context not in CONTEXTS:
        raise ValueError("unknown structural context")
    if not (1 <= current_block <= BLOCK_COUNT):
        raise ValueError("current_block outside frozen block range")

    by_block: dict[int, list[Mapping[str, Any]]] = {}
    for row in rows:
        block = int(row["block"])
        if block >= current_block:
            continue
        if structural_context(row["ranked_top5"]) != context:
            continue
        by_block.setdefault(block, []).append(row)

    return {
        block: rr
        for block, rr in sorted(by_block.items())
        if len(rr) >= MIN_CONTEXT_RACES_PER_BLOCK
    }


def context_training_score(
    rows: Iterable[Mapping[str, Any]],
    *,
    context: str,
    current_block: int,
) -> tuple[float, float] | None:
    blocks = qualifying_context_blocks(
        rows,
        context=context,
        current_block=current_block,
    )
    if len(blocks) < MIN_PRIOR_QUALIFYING_BLOCKS:
        return None

    block_rois: list[float] = []
    cumulative_return = 0
    cumulative_investment = 0
    for block in sorted(blocks):
        rr = blocks[block]
        gross = sum(formal_two_return_yen(row) for row in rr)
        investment = len(rr) * POINTS_PER_RACE * UNIT_YEN
        block_rois.append(gross / investment * 100.0)
        cumulative_return += gross
        cumulative_investment += investment

    return (
        float(median(block_rois)),
        float(cumulative_return / cumulative_investment * 100.0),
    )


def _validate_day(day_rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if len(day_rows) != DAILY_CANDIDATES:
        raise ValueError("each evaluable day must contain exact six frozen races")
    ordered = sorted(
        day_rows,
        key=lambda row: (int(row["daily_rank"]), str(row["race_id"])),
    )
    ranks = [int(row["daily_rank"]) for row in ordered]
    if ranks != list(range(1, DAILY_CANDIDATES + 1)):
        raise ValueError("daily ranks must be exactly 1..6")
    for row in ordered:
        float(row["race_score"])
        structural_context(row["ranked_top5"])
    return ordered


def choose_one_race(
    history_rows: Iterable[Mapping[str, Any]],
    *,
    day_rows: Sequence[Mapping[str, Any]],
    current_block: int,
) -> Mapping[str, Any]:
    ordered = _validate_day(day_rows)
    if not (1 <= current_block <= BLOCK_COUNT):
        raise ValueError("current_block outside frozen block range")

    # The first two chronological blocks use the current best-ranked race.
    if current_block <= WARMUP_BLOCKS:
        return ordered[0]

    history = list(history_rows)
    scored: list[tuple[tuple[float, float], Mapping[str, Any]]] = []
    for row in ordered:
        context = structural_context(row["ranked_top5"])
        score = context_training_score(
            history,
            context=context,
            current_block=current_block,
        )
        if score is not None:
            scored.append((score, row))

    # Sparse-history days fail closed to the current daily-rank-1 choice.
    if not scored:
        return ordered[0]

    scored.sort(
        key=lambda item: (
            -item[0][0],
            -item[0][1],
            -float(item[1]["race_score"]),
            int(item[1]["daily_rank"]),
            str(item[1]["race_id"]),
        )
    )
    return scored[0][1]


def contract_metadata() -> dict[str, Any]:
    return {
        "contract": "v4_daily_one_race_selector_v1",
        "contexts": list(CONTEXTS),
        "daily_candidates": DAILY_CANDIDATES,
        "selected_races_per_day": SELECTED_RACES_PER_DAY,
        "points_per_race": POINTS_PER_RACE,
        "unit_yen": UNIT_YEN,
        "block_count": BLOCK_COUNT,
        "warmup_blocks": WARMUP_BLOCKS,
        "min_context_races_per_block": MIN_CONTEXT_RACES_PER_BLOCK,
        "min_prior_qualifying_blocks": MIN_PRIOR_QUALIFYING_BLOCKS,
        "selection_metric": SELECTION_METRIC,
        "ticket_source": "frozen_ranked_top5_ranks_1_2",
        "current_race_score_tiebreak_only": True,
        "daily_rank_tiebreak_only": True,
        "zero_race_day_allowed": False,
        "more_than_one_race_allowed": False,
        "ticket_rerank_allowed": False,
        "market_input_allowed": False,
        "odds_gate_allowed": False,
        "venue_filter_allowed": False,
        "race_number_filter_allowed": False,
        "date_filter_allowed": False,
        "same_day_result_feedback_allowed": False,
        "stake_change_allowed": False,
        "production_change_allowed": False,
        "purchase_action": False,
    }
