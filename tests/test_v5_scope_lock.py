from research.v5_scope_lock import validate_scope


def test_scope_locks_current_v4_as_v5_baseline():
    x = validate_scope()
    fixed = x["core_baseline"]["fixed_contract"]
    assert fixed["course_coefficient"] == 0.50
    assert fixed["opponent_pressure_coefficient"] == 1.0
    assert fixed["motor2_beta"] == 0.06
    assert fixed["probability_temperature"] == 2.20
    assert fixed["formal_races"] == 6
    assert fixed["formal_tickets_per_race"] == 2
    assert fixed["selector_signals"] == [
        "head_p1", "head_margin", "top3_mass", "concentration"
    ]


def test_mid_october_gate_cannot_be_lowered():
    x = validate_scope()
    assert x["mandatory_evidence_tracks"]["formal_v4"]["required_resolved_days"] == 20
    assert x["mandatory_evidence_tracks"]["s03_m2"]["required_evaluated_observations"] == 100
    assert x["change_control"]["no_gate_lowering_to_meet_date"] is True
    assert x["change_control"]["new_feature_can_enter_20261015_core"] is False


def test_optional_layers_do_not_block_core():
    x = validate_scope()
    assert x["optional_layers"]["day_strength"]["required_for_core_freeze"] is False
    assert x["optional_layers"]["f_count"]["required_for_core_freeze"] is False
    assert x["optional_layers"]["f_count"]["live_activation_approved"] is False


def test_activation_remains_disabled():
    x = validate_scope()
    assert all(v is False for v in x["activation"].values())
