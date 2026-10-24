# -*- coding: utf-8 -*-
"""Frozen current-V4 exhibition-time-rank OOS contract.

Research only. The hypothesis, coefficient family, training rule and
interpretation gate are frozen before the first replay result is read.

The historical exhibition rows are retrospective copies of official pre-race
beforeinfo. They are acceptable for retrospective chronological OOS research,
but they are NOT prospective capture-time evidence. Any positive result must
therefore pass a fresh first-write-wins Forward shadow before Production review.
"""
from __future__ import annotations

import math
from typing import Mapping

VARIANTS = ("control", "exhibition_time_rank")
START_DATE = "2025-07-01"
END_DATE = "2026-09-22"
BLOCKS = 10
PURE_EVAL_START_BLOCK = 3
EXPECTED_CONTROL_DAYS = 432
FORMAL_TICKETS = 2
UNIT_YEN = 100

EXHIBITION_SNAPSHOT_LABEL = "historical"
COEFFICIENT_GRID = (0.0, 0.05, 0.10, 0.20)
MIN_POSITIVE_SELECTED_BLOCKS = 6
MIN_LOGLOSS_BETTER_BLOCKS = 6


def _zscore_complete_ranks(ranks: Mapping[int, int]) -> dict[int, float] | None:
    if tuple(sorted(ranks)) != (1, 2, 3, 4, 5, 6):
        return None
    values = []
    for lane in range(1, 7):
        try:
            rank = int(ranks[lane])
        except Exception:
            return None
        if rank not in range(1, 7):
            return None
        values.append(-float(rank))
    if sorted(int(ranks[lane]) for lane in range(1, 7)) != [1, 2, 3, 4, 5, 6]:
        return None
    mean = sum(values) / 6.0
    sd = math.sqrt(sum((x - mean) ** 2 for x in values) / 6.0)
    if sd < 1e-12:
        return None
    return {lane: (values[lane - 1] - mean) / sd for lane in range(1, 7)}


def adjust_base_raw(
    base_raw: Mapping[int, float],
    ranks: Mapping[int, int],
    coefficient: float,
) -> dict[int, float]:
    if tuple(sorted(base_raw)) != (1, 2, 3, 4, 5, 6):
        raise ValueError("base_raw must contain lanes 1..6")
    if coefficient not in COEFFICIENT_GRID:
        raise ValueError("coefficient outside frozen grid")
    z = _zscore_complete_ranks(ranks)
    if z is None or coefficient == 0.0:
        return {lane: float(base_raw[lane]) for lane in range(1, 7)}
    return {
        lane: float(base_raw[lane]) + coefficient * z[lane]
        for lane in range(1, 7)
    }


def contract_metadata() -> dict[str, object]:
    return {
        "variants": list(VARIANTS),
        "period": [START_DATE, END_DATE],
        "blocks": BLOCKS,
        "pure_eval_start_block": PURE_EVAL_START_BLOCK,
        "source_table": "v2_realtime_exhibition_snapshots",
        "snapshot_label": EXHIBITION_SNAPSHOT_LABEL,
        "feature": "exhibition_time_rank",
        "feature_requires_complete_rank_permutation": True,
        "missing_or_incomplete_feature": "neutral_control_distribution",
        "coefficient_grid": list(COEFFICIENT_GRID),
        "coefficient_selection": (
            "for each evaluation block, minimize first-place LogLoss on "
            "control-fixed rank1 full6 rows from strictly earlier canonical blocks only"
        ),
        "coefficient_tie_break": "smallest_coefficient",
        "same_block_outcomes_allowed_for_selection": False,
        "old_v22_or_bao_coefficients_reused": False,
        "historical_snapshot_is_prospective_timing_proof": False,
        "positive_result_requires_fresh_forward": True,
        "track_a_fixed_control_rank1": True,
        "track_b_variant_reselection": True,
        "result_query_after_all_candidate_variant_freezes_per_day": True,
        "odds_used": False,
        "ev_used": False,
        "threshold_search": False,
        "venue_filter_search": False,
        "race_band_filter_search": False,
        "production_change": False,
        "line": False,
        "purchase_action": False,
        "support_gate": {
            "track_a_aggregate_logloss_better": True,
            "track_a_aggregate_brier_better": True,
            "track_a_head_accuracy_better": True,
            "track_a_logloss_better_blocks_min": MIN_LOGLOSS_BETTER_BLOCKS,
            "positive_coefficient_blocks_min": MIN_POSITIVE_SELECTED_BLOCKS,
            "track_b_aggregate_logloss_not_worse": True,
            "track_b_aggregate_brier_not_worse": True,
            "track_b_head_accuracy_not_worse": True,
        },
    }
