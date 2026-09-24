# -*- coding: utf-8 -*-
"""Preregistered structural reranker contract for V4.

Goal: keep the exact current six selected races and exactly two tickets per race,
while allowing rank1 to be replaced only when a simple pre-result structural
state has robust earlier-block evidence.

This contract is pure/offline and does not use odds, market ranks, venue filters,
race-number filters, dates, DB state, LINE, or purchase actions.
"""
from __future__ import annotations

from statistics import median
from typing import Any, Iterable, Mapping, Sequence

CONTROL_PAIR = (1, 2)
PAIR_CANDIDATES = (
    (1, 2),
    (2, 3),
    (2, 4),
    (2, 5),
)
POINTS_PER_RACE = 2
CORE_RACES_PER_DAY = 6
UNIT_YEN = 100
BLOCK_COUNT = 10
WARMUP_BLOCKS = 2
MIN_PRIOR_RACES_PER_STATE = 40

DAILY_RANK_BUCKETS = (
    ("high", (1, 2)),
    ("mid", (3, 4)),
    ("low", (5, 6)),
)


def _daily_rank_bucket(rank: int) -> str:
    for label, ranks in DAILY_RANK_BUCKETS:
        if rank in ranks:
            return label
    raise ValueError("daily_rank must be 1..6")


def _top5_head_mode(ranked_top5: Sequence[str]) -> str:
    if len(ranked_top5) != 5 or len(set(ranked_top5)) != 5:
        raise ValueError("ranked_top5 must contain five unique frozen tickets")
    heads = []
    for ticket in ranked_top5:
        parts = str(ticket).split("-")
        if len(parts) != 3:
            raise ValueError("invalid trifecta ticket")
        lanes = tuple(int(x) for x in parts)
        if any(x < 1 or x > 6 for x in lanes) or len(set(lanes)) != 3:
            raise ValueError("invalid trifecta ticket")
        heads.append(lanes[0])
    return "single_head" if len(set(heads)) == 1 else "multi_head"


def structural_state(row: Mapping[str, Any]) -> tuple[str, str]:
    """Use only fields already frozen in the immutable long-history artifact."""
    return (
        _daily_rank_bucket(int(row["daily_rank"])),
        _top5_head_mode(row["ranked_top5"]),
    )


def freeze_pair(ranked_top5: Sequence[str], pair: tuple[int, int]) -> tuple[str, str]:
    if pair not in PAIR_CANDIDATES:
        raise ValueError("pair outside preregistered family")
    if len(ranked_top5) != 5 or len(set(ranked_top5)) != 5:
        raise ValueError("invalid frozen Top5")
    return (
        str(ranked_top5[pair[0] - 1]),
        str(ranked_top5[pair[1] - 1]),
    )


def realized_return_yen(row: Mapping[str, Any], pair: tuple[int, int]) -> int:
    actual = str(row["actual_trifecta"])
    payout = int(row["payout_yen"])
    if payout <= 0:
        raise ValueError("payout must be positive")
    return payout if actual in freeze_pair(row["ranked_top5"], pair) else 0


def roi_percent(rows: Iterable[Mapping[str, Any]], pair: tuple[int, int]) -> float:
    rr = list(rows)
    if not rr:
        raise ValueError("ROI requires at least one race")
    gross = sum(realized_return_yen(row, pair) for row in rr)
    investment = len(rr) * POINTS_PER_RACE * UNIT_YEN
    return gross / investment * 100.0


def prior_state_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    state: tuple[str, str],
    current_block: int,
) -> list[Mapping[str, Any]]:
    if not (1 <= current_block <= BLOCK_COUNT):
        raise ValueError("current_block outside frozen range")
    return [
        row
        for row in rows
        if int(row["block"]) < current_block and structural_state(row) == state
    ]


def _per_block_rois(
    rows: Sequence[Mapping[str, Any]],
    pair: tuple[int, int],
) -> list[float]:
    by_block: dict[int, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_block.setdefault(int(row["block"]), []).append(row)
    return [roi_percent(by_block[b], pair) for b in sorted(by_block)]


def choose_pair_for_state(
    rows: Iterable[Mapping[str, Any]],
    *,
    state: tuple[str, str],
    current_block: int,
) -> tuple[int, int]:
    """Choose a pair for one structural state using strictly earlier blocks.

    Blocks 1-2 are forced control. Later blocks switch away from control only
    when an alternative beats control on BOTH:
      - median prior-block ROI; and
      - cumulative prior-race ROI.

    Sparse states fail closed to control.
    """
    rows = list(rows)
    if current_block <= WARMUP_BLOCKS:
        return CONTROL_PAIR

    prior = prior_state_rows(
        rows,
        state=state,
        current_block=current_block,
    )
    if len(prior) < MIN_PRIOR_RACES_PER_STATE:
        return CONTROL_PAIR
    prior_blocks = sorted({int(row["block"]) for row in prior})
    if len(prior_blocks) < WARMUP_BLOCKS:
        return CONTROL_PAIR

    control_block_median = float(median(_per_block_rois(prior, CONTROL_PAIR)))
    control_cumulative = roi_percent(prior, CONTROL_PAIR)

    eligible: list[tuple[float, float, int, tuple[int, int]]] = []
    for pair in PAIR_CANDIDATES:
        if pair == CONTROL_PAIR:
            continue
        block_median = float(median(_per_block_rois(prior, pair)))
        cumulative = roi_percent(prior, pair)
        if (
            block_median > control_block_median
            and cumulative > control_cumulative
        ):
            # Higher median and cumulative are better. Lower replacement rank
            # is the conservative deterministic tie-break.
            eligible.append(
                (
                    block_median,
                    cumulative,
                    -pair[1],
                    pair,
                )
            )

    if not eligible:
        return CONTROL_PAIR
    return max(eligible)[3]


def choose_state_policy_for_block(
    rows: Iterable[Mapping[str, Any]],
    *,
    current_block: int,
) -> dict[tuple[str, str], tuple[int, int]]:
    rows = list(rows)
    states = [
        (rank_bucket, head_mode)
        for rank_bucket, _ in DAILY_RANK_BUCKETS
        for head_mode in ("single_head", "multi_head")
    ]
    return {
        state: choose_pair_for_state(
            rows,
            state=state,
            current_block=current_block,
        )
        for state in states
    }


def contract_metadata() -> dict[str, Any]:
    return {
        "contract": "v4_structural_conditional_reranker_v1",
        "source_fields": ["daily_rank", "ranked_top5", "chronological_block"],
        "states": {
            "daily_rank_buckets": {
                label: list(ranks) for label, ranks in DAILY_RANK_BUCKETS
            },
            "top5_head_mode": ["single_head", "multi_head"],
        },
        "control_pair": list(CONTROL_PAIR),
        "pair_candidates": [list(pair) for pair in PAIR_CANDIDATES],
        "rank2_always_retained": True,
        "points_per_race": POINTS_PER_RACE,
        "core_races_per_day": CORE_RACES_PER_DAY,
        "unit_yen": UNIT_YEN,
        "block_count": BLOCK_COUNT,
        "warmup_blocks": WARMUP_BLOCKS,
        "min_prior_races_per_state": MIN_PRIOR_RACES_PER_STATE,
        "switch_gate": "alt_median_prior_block_roi_gt_control_AND_alt_cumulative_roi_gt_control",
        "candidate_skip_allowed": False,
        "race_replacement_allowed": False,
        "odds_input_allowed": False,
        "market_rank_allowed": False,
        "venue_filter_allowed": False,
        "race_number_filter_allowed": False,
        "date_filter_allowed": False,
        "stake_change_allowed": False,
        "production_change_allowed": False,
        "purchase_action": False,
    }
