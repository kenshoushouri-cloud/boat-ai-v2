# -*- coding: utf-8 -*-
"""Preregistered V4 input-information ablation contract.

Research only. The purpose is to determine whether current V4 enrichments
improve or degrade first-place prediction and daily-rank-1 economics.

This contract freezes the candidate family before any new replay result is read.
"""
from __future__ import annotations

from typing import Any, Mapping

VARIANTS = (
    "control",
    "no_course",
    "no_opponent",
    "no_motor",
    "base_only",
)

START_DATE = "2025-07-01"
END_DATE = "2026-09-22"
BLOCKS = 10
PURE_EVAL_START_BLOCK = 3
DAILY_CONTROL_RANK = 1
FORMAL_TICKETS = 2
UNIT_YEN = 100


def variant_inputs(
    label: str,
    *,
    course_top3: Mapping[int, float],
    opponent_delta: Mapping[int, float] | None,
    motor_place2: Mapping[int, float],
) -> dict[str, Any]:
    if label not in VARIANTS:
        raise ValueError(f"unknown variant: {label}")

    if label == "control":
        return {
            "course_top3": dict(course_top3),
            "opponent_delta": None if opponent_delta is None else dict(opponent_delta),
            "motor_place2": dict(motor_place2),
        }
    if label == "no_course":
        return {
            "course_top3": {},
            "opponent_delta": None if opponent_delta is None else dict(opponent_delta),
            "motor_place2": dict(motor_place2),
        }
    if label == "no_opponent":
        return {
            "course_top3": dict(course_top3),
            "opponent_delta": None,
            "motor_place2": dict(motor_place2),
        }
    if label == "no_motor":
        return {
            "course_top3": dict(course_top3),
            "opponent_delta": None if opponent_delta is None else dict(opponent_delta),
            "motor_place2": {},
        }
    return {
        "course_top3": {},
        "opponent_delta": None,
        "motor_place2": {},
    }


def contract_metadata() -> dict[str, Any]:
    return {
        "contract": "v4_input_information_ablation_v1",
        "variants": list(VARIANTS),
        "period": {"start_date": START_DATE, "end_date": END_DATE},
        "blocks": BLOCKS,
        "pure_eval_start_block": PURE_EVAL_START_BLOCK,
        "daily_control_rank": DAILY_CONTROL_RANK,
        "formal_tickets": FORMAL_TICKETS,
        "unit_yen": UNIT_YEN,
        "track_a_fixed_control_race": True,
        "track_b_variant_reselection": True,
        "track_a_definition": (
            "freeze control six and control daily-rank-1 before result; "
            "evaluate every variant on that exact same race"
        ),
        "track_b_definition": (
            "freeze each variant's own daily top-six and daily-rank-1 before result"
        ),
        "primary_head_metrics": [
            "top1_head_accuracy",
            "head_log_loss",
            "head_brier",
        ],
        "secondary_ticket_metrics": [
            "formal_top2_hit_rate",
            "roi_percent",
            "profit_yen",
            "profitable_day_rate",
            "max_drawdown_yen",
        ],
        "report_feature_coverage": True,
        "same_source_cutoff_jst": "08:15",
        "same_exact_six_day_rule": True,
        "result_after_freeze_only": True,
        "odds_used": False,
        "ev_used": False,
        "threshold_search": False,
        "coefficient_retune": False,
        "new_feature_added": False,
        "production_change": False,
        "line": False,
        "purchase_action": False,
    }
