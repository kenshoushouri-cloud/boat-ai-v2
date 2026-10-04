# -*- coding: utf-8 -*-
"""Frozen research-only V5 matched-contract candidate and shared time split.

This file is intentionally pure and contains no database/Railway/outcome access.
The specification is frozen before the matched-contract historical economics run.
"""
from __future__ import annotations

from typing import Any

from research.matched_contract_backtest_preflight import (
    TIME_SPLIT_CONTRACT,
    V5_SPEC_CONTRACT,
)


V5_CANDIDATE_ID = "V5_M2_TOP2_BOTH_POSITIVE_V1"
FREEZE_DATE = "2026-10-04"


def v5_candidate_manifest() -> dict[str, Any]:
    return {
        "contract": V5_SPEC_CONTRACT,
        "candidate_id": V5_CANDIDATE_ID,
        "freeze_date": FREEZE_DATE,
        "frozen_before_backtest_results": True,
        "production_activation_allowed": False,
        "base_generation": "V4",
        "base_implementation": "research.candidate_discovery_v4_contract",
        "base_probability_contract_unchanged": True,
        "base_structural_selector_unchanged": True,
        "odds_read_for_selection": False,
        "expected_value_filter": False,
        "formal_races_before_overlay": 6,
        "formal_tickets_per_selected_race": 2,
        "unit_yen_per_ticket": 100,
        "investment_yen_per_selected_race": 200,
        "comparison_delta": [
            "apply_frozen_motor2_ticket_score_to_v4_top2",
            "keep_race_only_when_both_v4_top2_ticket_scores_gt_0",
        ],
        "motor2_overlay": {
            "source_rule": "S03_M2_POSITIVE_V1",
            "score_inputs": "motor_place2_rate_only",
            "lane_standardization": "within_race_population_zscore_all_6_lanes",
            "ticket_position_weights": [1.0, 0.6, 0.3],
            "ticket_pass_condition": "score > 0.0",
            "race_pass_condition": "both frozen V4 TOP2 tickets pass",
            "odds_used": False,
            "ev_used": False,
        },
        "prospective_admission_gate": {
            "formal_v4_resolved_days_min": 20,
            "s03_m2_officially_evaluated_min": 100,
            "evidence_contract_clean_required": True,
            "historical_reconstruction_counts_toward_gate": False,
        },
        "economics_policy": {
            "target_races_per_day_min_reference": 1,
            "monthly_profit_target_yen": 50000,
            "do_not_relax_rule_to_force_volume_or_profit": True,
            "stake_scaling_authorized": False,
        },
        "safety": {
            "research_only": True,
            "production_change": False,
            "purchase_action": False,
            "line_send": False,
            "railway_change": False,
            "database_write": False,
            "post_outcome_retune": False,
        },
    }


def shared_time_split_manifest() -> dict[str, Any]:
    """Chronological split aligned to historical Course snapshot application terms."""
    return {
        "contract": TIME_SPLIT_CONTRACT,
        "freeze_date": FREEZE_DATE,
        "frozen_before_backtest_results": True,
        "shared_by": ["V4", V5_CANDIDATE_ID],
        "no_retune_between_windows": True,
        "windows": [
            {
                "name": "TRAIN_REFERENCE",
                "start_date": "2025-07-01",
                "end_date": "2025-12-31",
            },
            {
                "name": "VALIDATION",
                "start_date": "2026-01-01",
                "end_date": "2026-06-30",
            },
            {
                "name": "OOS",
                "start_date": "2026-07-01",
                "end_date": "2026-09-30",
            },
        ],
        "reporting": {
            "overall": True,
            "by_window": True,
            "by_month": True,
            "metrics": [
                "selected_races",
                "tickets",
                "investment_yen",
                "return_yen",
                "profit_yen",
                "roi_pct",
                "hit_rate_pct",
                "max_drawdown_yen",
                "max_losing_streak",
                "active_days",
                "races_per_active_day",
            ],
        },
    }


def frozen_contract() -> dict[str, Any]:
    return {
        "candidate": v5_candidate_manifest(),
        "time_split": shared_time_split_manifest(),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(frozen_contract(), ensure_ascii=False, indent=2, sort_keys=True))
    print("V5_MATCHED_BACKTEST_CONTRACT_RESULT=FROZEN_RESEARCH_ONLY")
