# -*- coding: utf-8 -*-
"""Frozen contract for the first V4 economic reranker experiment.

This module is intentionally pure/offline. It defines only the rank-pair policy
used by the later historical walk-forward evaluator.

Primary question:
Can we keep the exact same six V4 races and exactly two tickets per race, but
replace the fixed (rank1, rank2) pair with a pair chosen from the existing frozen
Top5 using *only earlier chronological blocks*?

No market data, venue filters, race-number filters, date filters, candidate
skips, model coefficient changes, or stake changes are part of this contract.
"""
from __future__ import annotations

from itertools import combinations
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

TOP5_RANKS = (1, 2, 3, 4, 5)
CONTROL_PAIR = (1, 2)
PAIR_CANDIDATES = tuple(combinations(TOP5_RANKS, 2))
POINTS_PER_RACE = 2
CORE_RACES_PER_DAY = 6
UNIT_YEN = 100
BLOCK_COUNT = 10
WARMUP_BLOCKS = 2

SELECTION_METRIC = (
    "max_median_prior_block_roi_then_cumulative_roi_then_control_distance"
)


def _ticket_at_rank(ranked_top5: Sequence[str], rank: int) -> str:
    if len(ranked_top5) != 5 or len(set(ranked_top5)) != 5:
        raise ValueError("ranked_top5 must contain five unique frozen tickets")
    if rank not in TOP5_RANKS:
        raise ValueError("rank outside frozen Top5")
    return str(ranked_top5[rank - 1])


def freeze_pair(
    ranked_top5: Sequence[str],
    pair: tuple[int, int],
) -> tuple[str, str]:
    if pair not in PAIR_CANDIDATES:
        raise ValueError("pair must be one of the ten frozen Top5 rank pairs")
    return (
        _ticket_at_rank(ranked_top5, pair[0]),
        _ticket_at_rank(ranked_top5, pair[1]),
    )


def realized_return_yen(
    row: Mapping[str, Any],
    pair: tuple[int, int],
) -> int:
    tickets = freeze_pair(row["ranked_top5"], pair)
    actual = str(row["actual_trifecta"])
    payout = int(row["payout_yen"])
    if payout <= 0:
        raise ValueError("payout_yen must be positive")
    return payout if actual in tickets else 0


def block_roi_percent(
    rows: Iterable[Mapping[str, Any]],
    pair: tuple[int, int],
) -> float:
    rr = list(rows)
    if not rr:
        raise ValueError("block requires at least one race")
    gross = sum(realized_return_yen(row, pair) for row in rr)
    investment = len(rr) * POINTS_PER_RACE * UNIT_YEN
    return gross / investment * 100.0


def _control_distance(pair: tuple[int, int]) -> int:
    return abs(pair[0] - CONTROL_PAIR[0]) + abs(pair[1] - CONTROL_PAIR[1])


def pair_training_score(
    rows: Iterable[Mapping[str, Any]],
    *,
    pair: tuple[int, int],
    current_block: int,
) -> tuple[float, float, int, int, int]:
    if not (1 <= current_block <= BLOCK_COUNT):
        raise ValueError("current_block outside frozen block range")
    prior = [row for row in rows if int(row["block"]) < current_block]
    if not prior:
        raise ValueError("no prior rows")

    by_block: dict[int, list[Mapping[str, Any]]] = {}
    for row in prior:
        block = int(row["block"])
        by_block.setdefault(block, []).append(row)

    block_rois = [
        block_roi_percent(by_block[block], pair)
        for block in sorted(by_block)
    ]
    cumulative_roi = block_roi_percent(prior, pair)

    # Higher is better for the first two terms. The remaining negative terms
    # create deterministic conservative tie breaks: closer to current (1,2),
    # then lower rank numbers.
    return (
        float(median(block_rois)),
        float(cumulative_roi),
        -_control_distance(pair),
        -pair[0],
        -pair[1],
    )


def choose_pair_for_block(
    rows: Iterable[Mapping[str, Any]],
    *,
    current_block: int,
) -> tuple[int, int]:
    rows = list(rows)
    if not (1 <= current_block <= BLOCK_COUNT):
        raise ValueError("current_block outside frozen block range")
    if current_block <= WARMUP_BLOCKS:
        return CONTROL_PAIR

    scores = {
        pair: pair_training_score(
            rows,
            pair=pair,
            current_block=current_block,
        )
        for pair in PAIR_CANDIDATES
    }
    return max(PAIR_CANDIDATES, key=lambda pair: scores[pair])


def contract_metadata() -> dict[str, Any]:
    return {
        "contract": "v4_economic_reranker_rank_pair_v1",
        "top5_ranks": list(TOP5_RANKS),
        "control_pair": list(CONTROL_PAIR),
        "pair_candidates": [list(pair) for pair in PAIR_CANDIDATES],
        "points_per_race": POINTS_PER_RACE,
        "core_races_per_day": CORE_RACES_PER_DAY,
        "unit_yen": UNIT_YEN,
        "block_count": BLOCK_COUNT,
        "warmup_blocks": WARMUP_BLOCKS,
        "selection_metric": SELECTION_METRIC,
        "candidate_skip_allowed": False,
        "race_replacement_allowed": False,
        "market_input_allowed": False,
        "venue_filter_allowed": False,
        "race_number_filter_allowed": False,
        "date_filter_allowed": False,
        "stake_change_allowed": False,
        "production_change_allowed": False,
        "purchase_action": False,
    }
