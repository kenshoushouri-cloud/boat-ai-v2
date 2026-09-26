# -*- coding: utf-8 -*-
"""Frozen V4 course-entry error-attribution contract.

Research diagnostic only. Actual start course is outcome-time evidence and is
NEVER supplied to the predictor in this experiment.
"""
START_DATE = "2025-07-01"
END_DATE = "2026-09-22"
BLOCKS = 10
PURE_EVAL_START_BLOCK = 3
EXPECTED_CONTROL_DAYS = 432
OFFICIAL_RESULT_ENTRY_SOURCE = "official_k_file"


def contract_metadata():
    return {
        "purpose": "error_attribution_only",
        "actual_start_course_is_predictor_input": False,
        "control_model": "current_v4_unchanged",
        "source": "v2_result_entries official_k_file",
        "result_and_course_query_after_selection_freeze": True,
        "strata": [
            "no_course_change",
            "any_course_change",
            "predicted_head_not_moved",
            "predicted_head_moved",
            "lane1_not_displaced",
            "lane1_displaced",
            "winner_not_moved",
            "winner_moved",
        ],
        "threshold_search": False,
        "coefficient_retune": False,
        "odds_used": False,
        "ev_used": False,
        "production_change": False,
        "line": False,
        "purchase_action": False,
    }
