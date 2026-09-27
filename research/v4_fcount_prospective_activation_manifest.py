# -*- coding: utf-8 -*-
"""Pure activation manifest for future approved prospective F-count capture.

No I/O is performed here. This freezes the allowed read shape, ordering,
fail-closed behavior, persistence boundary, and rollback/stop conditions.
"""
from __future__ import annotations

MANIFEST = {
    "contract": "V4_FCOUNT_PROSPECTIVE_ACTIVATION_MANIFEST_V1",
    "activation_performed": False,
    "approval_required": True,
    "scope": "future_target_days_only",
    "historical_backfill_allowed": False,
    "historical_coefficient_search_allowed": False,
    "formal_v4_must_exist_first": True,
    "formal_v4_mutation_allowed": False,
    "formal_v4_failure_on_companion_failure": False,
    "source_cutoff_jst": "08:15",
    "capture_order": [
        "formal_v4_prospective_freeze_completed",
        "formal_v4_core_sha256_frozen",
        "read_exact_formal_six_race_ids",
        "read_exact_36_fcount_rows",
        "validate_before_all_six_deadlines",
        "build_separate_hash_bound_companion_in_memory",
        "persist_companion_artifact_only",
    ],
    "allowed_db_read_sql": (
        "select race_id,lane,f_count "
        "from v2_race_entries "
        "where race_id=any(%s) "
        "order by race_id,lane"
    ),
    "db_transaction": "read_only",
    "db_write_allowed": False,
    "required_rows": 36,
    "required_races": 6,
    "required_lanes_per_race": [1, 2, 3, 4, 5, 6],
    "f_count_type": "exact_nonnegative_integer",
    "artifact": {
        "separate_from_formal_v4": True,
        "binds_formal_core_sha256": True,
        "contains_outcomes": False,
        "contains_odds": False,
        "contains_payouts": False,
        "purchase_action": False,
        "promotion_allowed": False,
    },
    "fail_closed_conditions": [
        "formal_artifact_missing_or_ineligible",
        "formal_core_hash_missing_or_changed",
        "capture_before_formal_freeze",
        "capture_before_08_15_jst",
        "capture_at_or_after_any_core_deadline",
        "row_count_not_36",
        "race_set_not_exact_formal_six",
        "lane_set_not_exact_1_to_6_per_race",
        "f_count_missing_negative_boolean_or_noninteger",
        "outcome_like_field_present",
    ],
    "on_failure": {
        "write_companion": False,
        "rewrite_formal_v4": False,
        "change_formal_selection": False,
        "change_tickets": False,
        "send_line": False,
        "purchase": False,
    },
    "stop_conditions_after_activation": [
        "formal_core_hash_mismatch",
        "any_post_deadline_capture",
        "any_db_write_attempt",
        "any_result_or_payout_field_observed",
        "any_companion_data_outside_exact_formal_six",
    ],
    "unchanged_requirements": [
        "course_coefficient_0_50",
        "opponent_pressure_1_0_first_place_only",
        "motor2_beta_0_06",
        "temperature_2_20",
        "selector_head_p1_head_margin_top3_mass_concentration",
        "formal_top6",
        "formal_top2",
        "stake",
        "purchase_action_false",
    ],
}


def validate_manifest() -> dict:
    if MANIFEST["activation_performed"] is not False:
        raise ValueError("design manifest cannot claim activation")
    if MANIFEST["approval_required"] is not True:
        raise ValueError("explicit approval gate must remain")
    if MANIFEST["historical_backfill_allowed"] is not False:
        raise ValueError("historical backfill forbidden")
    if MANIFEST["db_write_allowed"] is not False:
        raise ValueError("DB writes forbidden")
    if MANIFEST["required_rows"] != 36 or MANIFEST["required_races"] != 6:
        raise ValueError("exact 36 rows / six races required")
    if MANIFEST["artifact"]["separate_from_formal_v4"] is not True:
        raise ValueError("companion must remain separate")
    if MANIFEST["artifact"]["purchase_action"] is not False:
        raise ValueError("purchase must remain false")
    return MANIFEST


if __name__ == "__main__":
    import json
    print(json.dumps(validate_manifest(), ensure_ascii=False, indent=2, sort_keys=True))
