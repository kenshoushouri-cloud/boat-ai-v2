# -*- coding: utf-8 -*-
"""Frozen V4 strict-prior-ST missing-information contract.

Research only. This family is frozen before the first replay result is read.

The feature is deliberately morning-safe:
- source is official v2_result_entries from races on dates STRICTLY before target day;
- same-day prior races are excluded even if they would have finished before a later target race;
- the latest eligible prior official ST per racer is used;
- adjustment thresholds/weights are copied exactly from the already-frozen July
  previous-ST no-odds family. No new grid or coefficient search is allowed.
"""
from __future__ import annotations

from typing import Mapping

VARIANTS = ("control", "strict_prior_st")
START_DATE = "2025-07-01"
END_DATE = "2026-09-22"
BLOCKS = 10
PURE_EVAL_START_BLOCK = 3
EXPECTED_CONTROL_DAYS = 432
FORMAL_TICKETS = 2
UNIT_YEN = 100

FAST_THRESHOLD = 0.08
FAST_BONUS = 0.08
SLOW_THRESHOLD = 0.18
SLOW_PENALTY = 0.18

OFFICIAL_RESULT_ENTRY_SOURCE = "official_k_file"


def prior_st_adjustment(value: object) -> float:
    if value is None:
        return 0.0
    try:
        st = float(value)
    except Exception:
        return 0.0
    if st <= FAST_THRESHOLD:
        return FAST_BONUS
    if st >= SLOW_THRESHOLD:
        return -SLOW_PENALTY
    return 0.0


def adjust_base_raw(
    base_raw: Mapping[int, float],
    prior_st_by_lane: Mapping[int, float],
) -> dict[int, float]:
    if tuple(sorted(base_raw)) != (1, 2, 3, 4, 5, 6):
        raise ValueError("base_raw must contain lanes 1..6")
    return {
        lane: float(base_raw[lane]) + prior_st_adjustment(prior_st_by_lane.get(lane))
        for lane in range(1, 7)
    }


def contract_metadata() -> dict[str, object]:
    return {
        "variants": list(VARIANTS),
        "source": "v2_result_entries official prior-day facts only",
        "same_day_results_allowed": False,
        "source_date_rule": "prior_race_date < target_date",
        "official_source_required": OFFICIAL_RESULT_ENTRY_SOURCE,
        "fast_threshold": FAST_THRESHOLD,
        "fast_bonus": FAST_BONUS,
        "slow_threshold": SLOW_THRESHOLD,
        "slow_penalty": SLOW_PENALTY,
        "threshold_search": False,
        "coefficient_retune": False,
        "odds_used": False,
        "ev_used": False,
        "track_a_fixed_control_rank1": True,
        "track_b_variant_reselection": True,
        "result_query_after_both_variant_freezes": True,
        "missing_prior_st_is_neutral": True,
        "availability_strata_predeclared": ["all", "any", "full6"],
        "production_change": False,
        "line": False,
        "purchase_action": False,
    }
