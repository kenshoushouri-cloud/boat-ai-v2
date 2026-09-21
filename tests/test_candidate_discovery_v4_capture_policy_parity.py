# -*- coding: utf-8 -*-
"""Fail closed if the Draft formal-core hash policy drifts from V4 contract constants."""

from research import candidate_discovery_v4_contract as v4
from research.candidate_discovery_v4_capture_arbiter import (
    CORE_RACES,
    CORE_TICKETS,
    EXPECTED_FORMAL_POLICY,
)


def main() -> None:
    policy = EXPECTED_FORMAL_POLICY
    assert policy["course_coefficient"] == v4.COURSE_COEF
    assert policy["course_missing_lane"] == "neutral"
    assert policy["course_source_cutoff_jst"] == "08:15"
    assert policy["opponent_pressure_coefficient"] == v4.OPPONENT_COEF
    assert policy["opponent_pressure_role"] == "first_place_only"
    assert policy["motor2_beta"] == v4.MOTOR_BETA
    assert tuple(policy["motor2_position_weights"]) == tuple(v4.MOTOR_POS_W)
    assert policy["core_races_per_day"] == v4.CORE_RACES
    assert policy["core_tickets_per_race"] == v4.CORE_TICKETS
    assert policy["expected_value_filter"] is False
    assert policy["odds_filter"] is False
    assert policy["odds_read"] is False
    assert CORE_RACES == v4.CORE_RACES
    assert CORE_TICKETS == v4.CORE_RACES * v4.CORE_TICKETS
    print("CANDIDATE_V4_CAPTURE_POLICY_PARITY=PASS")


if __name__ == "__main__":
    main()
