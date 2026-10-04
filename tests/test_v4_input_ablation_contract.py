# -*- coding: utf-8 -*-
from research.v4_input_ablation_contract import (
    VARIANTS,
    contract_metadata,
    variant_inputs,
)


COURSE = {1: 40.0, 2: 30.0}
OPP = {lane: lane / 100.0 for lane in range(1, 7)}
MOTOR = {lane: 20.0 + lane for lane in range(1, 7)}


def test_variant_family_is_small_and_frozen():
    assert VARIANTS == (
        "control",
        "no_course",
        "no_opponent",
        "no_motor",
        "base_only",
    )


def test_control_preserves_all_inputs():
    got = variant_inputs(
        "control",
        course_top3=COURSE,
        opponent_delta=OPP,
        motor_place2=MOTOR,
    )
    assert got["course_top3"] == COURSE
    assert got["opponent_delta"] == OPP
    assert got["motor_place2"] == MOTOR


def test_single_feature_ablations_remove_only_one_layer():
    no_course = variant_inputs(
        "no_course",
        course_top3=COURSE,
        opponent_delta=OPP,
        motor_place2=MOTOR,
    )
    assert no_course["course_top3"] == {}
    assert no_course["opponent_delta"] == OPP
    assert no_course["motor_place2"] == MOTOR

    no_opp = variant_inputs(
        "no_opponent",
        course_top3=COURSE,
        opponent_delta=OPP,
        motor_place2=MOTOR,
    )
    assert no_opp["course_top3"] == COURSE
    assert no_opp["opponent_delta"] is None
    assert no_opp["motor_place2"] == MOTOR

    no_motor = variant_inputs(
        "no_motor",
        course_top3=COURSE,
        opponent_delta=OPP,
        motor_place2=MOTOR,
    )
    assert no_motor["course_top3"] == COURSE
    assert no_motor["opponent_delta"] == OPP
    assert no_motor["motor_place2"] == {}


def test_base_only_removes_all_three_enrichments():
    got = variant_inputs(
        "base_only",
        course_top3=COURSE,
        opponent_delta=OPP,
        motor_place2=MOTOR,
    )
    assert got == {
        "course_top3": {},
        "opponent_delta": None,
        "motor_place2": {},
    }


def test_contract_forbids_retune_and_result_leakage():
    meta = contract_metadata()
    assert meta["track_a_fixed_control_race"] is True
    assert meta["track_b_variant_reselection"] is True
    assert meta["result_after_freeze_only"] is True
    assert meta["threshold_search"] is False
    assert meta["coefficient_retune"] is False
    assert meta["new_feature_added"] is False
    assert meta["odds_used"] is False
    assert meta["ev_used"] is False
    assert meta["production_change"] is False
    assert meta["purchase_action"] is False
