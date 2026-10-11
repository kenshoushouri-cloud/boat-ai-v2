# -*- coding: utf-8 -*-
"""Preregistered contract for a structure-conditioned V4 rank reranker.

The policy keeps the exact same six selected races and exactly two 100-yen
tickets per race. It uses no market/odds gate and no candidate skip.

Only two pre-result structural features derived from the already-frozen Top5 are
used to define four broad contexts:
- whether the Top3 tickets use one first-place head or multiple heads;
- whether Top1 and Top2 share the same first-second prefix.

For each context, rank-level economic performance is learned from strictly prior
chronological blocks. The two ranks with the strongest robust prior economics
are selected for the entire next block. Current-block outcomes are never visible
to the selector.
"""
from __future__ import annotations

from statistics import median
from typing import Any, Iterable, Mapping, Sequence

TOP5_RANKS = (1, 2, 3, 4, 5)
CONTROL_RANKS = (1, 2)
CORE_RACES_PER_DAY = 6
POINTS_PER_RACE = 2
UNIT_YEN = 100
BLOCK_COUNT = 10
WARMUP_BLOCKS = 2
MIN_CONTEXT_RACES_PER_BLOCK = 10
MIN_PRIOR_QUALIFYING_BLOCKS = 2

SELECTION_METRIC = (
    "rank_median_prior_block_roi_then_cumulative_roi_then_lower_rank"
)


def _parts(ticket: str) -> tuple[str, str, str]:
    parts = str(ticket).split("-")
    if len(parts) != 3 or len(set(parts)) != 3:
        raise ValueError(f"invalid trifecta ticket: {ticket}")
    return parts[0], parts[1], parts[2]


def structural_context(ranked_top5: Sequence[str]) -> str:
    if len(ranked_top5) != 5 or len(set(ranked_top5)) != 5:
        raise ValueError("ranked_top5 must contain five unique frozen tickets")
    parsed = [_parts(ticket) for ticket in ranked_top5]
    top3_heads = len({parts[0] for parts in parsed[:3]})
    head_bucket = "H1" if top3_heads == 1 else "HM"
    prefix_same = parsed[0][:2] == parsed[1][:2]
    prefix_bucket = "P1" if prefix_same else "P0"
    return f"{head_bucket}_{prefix_bucket}"


CONTEXTS = ("H1_P0", "H1_P1", "HM_P0", "HM_P1")


def rank_ticket(ranked_top5: Sequence[str], rank: int) -> str:
    if rank not in TOP5_RANKS:
        raise ValueError("rank outside Top5")
    if len(ranked_top5) != 5 or len(set(ranked_top5)) != 5:
        raise ValueError("ranked_top5 must contain five unique frozen tickets")
    return str(ranked_top5[rank - 1])


def rank_return_yen(row: Mapping[str, Any], rank: int) -> int:
    ticket = rank_ticket(row["ranked_top5"], rank)
    payout = int(row["payout_yen"])
    if payout <= 0:
        raise ValueError("payout_yen must be positive")
    return payout if ticket == str(row["actual_trifecta"]) else 0


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


def rank_training_score(
    rows: Iterable[Mapping[str, Any]],
    *,
    context: str,
    rank: int,
    current_block: int,
) -> tuple[float, float, int]:
    blocks = qualifying_context_blocks(
        rows,
        context=context,
        current_block=current_block,
    )
    if len(blocks) < MIN_PRIOR_QUALIFYING_BLOCKS:
        raise ValueError("insufficient qualifying prior blocks")

    block_rois: list[float] = []
    cumulative_return = 0
    cumulative_races = 0
    for block in sorted(blocks):
        rr = blocks[block]
        gross = sum(rank_return_yen(row, rank) for row in rr)
        block_rois.append(gross / (len(rr) * UNIT_YEN) * 100.0)
        cumulative_return += gross
        cumulative_races += len(rr)

    cumulative_roi = (
        cumulative_return / (cumulative_races * UNIT_YEN) * 100.0
    )
    return (
        float(median(block_rois)),
        float(cumulative_roi),
        -rank,
    )


def choose_ranks_for_context(
    rows: Iterable[Mapping[str, Any]],
    *,
    context: str,
    current_block: int,
) -> tuple[int, int]:
    rows = list(rows)
    if current_block <= WARMUP_BLOCKS:
        return CONTROL_RANKS

    blocks = qualifying_context_blocks(
        rows,
        context=context,
        current_block=current_block,
    )
    if len(blocks) < MIN_PRIOR_QUALIFYING_BLOCKS:
        return CONTROL_RANKS

    scores = {
        rank: rank_training_score(
            rows,
            context=context,
            rank=rank,
            current_block=current_block,
        )
        for rank in TOP5_RANKS
    }
    ordered = sorted(
        TOP5_RANKS,
        key=lambda rank: scores[rank],
        reverse=True,
    )
    chosen = tuple(sorted(ordered[:2]))
    return chosen  # type: ignore[return-value]


def choose_ranks_for_race(
    rows: Iterable[Mapping[str, Any]],
    *,
    ranked_top5: Sequence[str],
    current_block: int,
) -> tuple[int, int]:
    context = structural_context(ranked_top5)
    return choose_ranks_for_context(
        rows,
        context=context,
        current_block=current_block,
    )


def contract_metadata() -> dict[str, Any]:
    return {
        "contract": "v4_structural_rank_reranker_v1",
        "contexts": list(CONTEXTS),
        "context_features": [
            "top3_head_single_vs_multi",
            "top2_same_first_second_prefix",
        ],
        "top5_ranks": list(TOP5_RANKS),
        "control_ranks": list(CONTROL_RANKS),
        "core_races_per_day": CORE_RACES_PER_DAY,
        "points_per_race": POINTS_PER_RACE,
        "unit_yen": UNIT_YEN,
        "block_count": BLOCK_COUNT,
        "warmup_blocks": WARMUP_BLOCKS,
        "min_context_races_per_block": MIN_CONTEXT_RACES_PER_BLOCK,
        "min_prior_qualifying_blocks": MIN_PRIOR_QUALIFYING_BLOCKS,
        "selection_metric": SELECTION_METRIC,
        "daily_rank_used_for_selection": False,
        "market_input_allowed": False,
        "odds_gate_allowed": False,
        "candidate_skip_allowed": False,
        "race_replacement_allowed": False,
        "venue_filter_allowed": False,
        "race_number_filter_allowed": False,
        "date_filter_allowed": False,
        "stake_change_allowed": False,
        "production_change_allowed": False,
        "purchase_action": False,
    }
