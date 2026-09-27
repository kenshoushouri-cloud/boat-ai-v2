# -*- coding: utf-8 -*-
"""Pure V5 research scope lock for the 2026-10-15 core milestone."""
from __future__ import annotations

from copy import deepcopy

SCOPE = {
    "contract": "V5_RESEARCH_SCOPE_LOCK_V1",
    "locked_on": "2026-09-27",
    "target_core_freeze_review": "2026-10-15",
    "production_generation": "V4",
    "research_generation": "V5",
    "core_baseline": {
        "probability_inputs": [
            "racer_class",
            "national_win_rate",
            "national_place2_rate",
            "local_place2_rate",
            "avg_st",
            "venue_course_bias",
            "racer_course",
            "opponent_pressure",
            "motor_place2_rate",
        ],
        "fixed_contract": {
            "course_coefficient": 0.50,
            "opponent_pressure_coefficient": 1.0,
            "opponent_pressure_role": "first_place_only",
            "motor2_beta": 0.06,
            "probability_temperature": 2.20,
            "selector_signals": [
                "head_p1",
                "head_margin",
                "top3_mass",
                "concentration",
            ],
            "formal_races": 6,
            "formal_tickets_per_race": 2,
            "odds_read_for_selection": False,
            "expected_value_filter": False,
        },
    },
    "mandatory_evidence_tracks": {
        "formal_v4": {
            "required_resolved_days": 20,
            "role": "baseline_forward_evidence",
        },
        "s03_m2": {
            "required_evaluated_observations": 100,
            "role": "independent_forward_evidence",
        },
    },
    "optional_layers": {
        "day_strength": {
            "required_for_core_freeze": False,
            "admission_gate": {
                "future_resolved_days": 10,
                "keep_days": 3,
                "skip_days": 3,
            },
            "if_not_ready": "remain_shadow_only",
        },
        "f_count": {
            "required_for_core_freeze": False,
            "live_activation_approved": False,
            "historical_backfill_allowed": False,
            "historical_coefficient_search_allowed": False,
            "if_not_ready": "defer_without_blocking_core",
        },
    },
    "deferred_from_v5_core": [
        "recent_form",
        "l_count",
        "exhibition_st",
        "exhibition_time",
        "weather_water",
        "odds_ev_selector",
        "new_unpreregistered_features",
    ],
    "change_control": {
        "new_feature_can_enter_20261015_core": False,
        "exception": (
            "only an already-listed optional layer may be admitted if its "
            "pre-existing prospective gate is naturally satisfied"
        ),
        "no_gate_lowering_to_meet_date": True,
        "no_post_outcome_retuning": True,
    },
    "activation": {
        "automatic_production_promotion": False,
        "automatic_model_change": False,
        "automatic_selector_change": False,
        "automatic_stake_change": False,
        "line_send": False,
        "purchase_action": False,
    },
}


def validate_scope() -> dict:
    x = deepcopy(SCOPE)
    fixed = x["core_baseline"]["fixed_contract"]
    if fixed["formal_races"] != 6 or fixed["formal_tickets_per_race"] != 2:
        raise ValueError("formal TOP6/TOP2 contract drift")
    if fixed["odds_read_for_selection"] is not False:
        raise ValueError("odds must not enter the core selector")
    if fixed["expected_value_filter"] is not False:
        raise ValueError("EV gate must remain outside the core selector")
    if x["mandatory_evidence_tracks"]["formal_v4"]["required_resolved_days"] != 20:
        raise ValueError("V4 V5-core gate drift")
    if x["mandatory_evidence_tracks"]["s03_m2"]["required_evaluated_observations"] != 100:
        raise ValueError("S03 V5-core gate drift")
    if x["change_control"]["no_gate_lowering_to_meet_date"] is not True:
        raise ValueError("scope lock must forbid deadline-driven gate lowering")
    if x["activation"]["purchase_action"] is not False:
        raise ValueError("purchase must remain disabled")
    return x


if __name__ == "__main__":
    import json
    print(json.dumps(validate_scope(), ensure_ascii=False, indent=2, sort_keys=True))
