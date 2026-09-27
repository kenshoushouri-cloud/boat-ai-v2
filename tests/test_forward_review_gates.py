from research.forward_review_gates import (
    current_baseline,
    day_strength_gate,
    s03_m2_gate,
    v4_formal_gate,
)


def test_current_baseline_matches_frozen_contract():
    x = current_baseline()
    assert x["v4_formal"]["current"] == 6
    assert x["v4_formal"]["next_gate"] == 10
    assert x["v4_formal"]["remaining"] == 4
    assert x["s03_m2"]["current"] == 53
    assert x["s03_m2"]["remaining"] == 47
    assert x["day_strength"]["status"] == "COLLECTING"
    assert x["purchase_action"] is False


def test_v4_gates_are_exactly_10_20_30():
    assert v4_formal_gate(9)["next_gate"] == 10
    assert v4_formal_gate(10)["next_gate"] == 20
    assert v4_formal_gate(20)["next_gate"] == 30
    assert v4_formal_gate(30)["next_gate"] is None


def test_s03_only_full_gate_is_100():
    assert s03_m2_gate(99)["status"] == "COLLECTING"
    assert s03_m2_gate(99)["remaining"] == 1
    assert s03_m2_gate(100)["status"] == "FULL_REVIEW_READY"
    assert s03_m2_gate(100)["remaining"] == 0


def test_day_strength_requires_all_three_frozen_conditions():
    assert day_strength_gate(10, 3, 2)["status"] == "COLLECTING"
    assert day_strength_gate(10, 2, 3)["status"] == "COLLECTING"
    assert day_strength_gate(9, 3, 3)["status"] == "COLLECTING"
    ready = day_strength_gate(10, 3, 3)
    assert ready["status"] == "DESCRIPTIVE_REVIEW_READY"
    assert ready["formal_action_changed"] is False
    assert ready["promotion_allowed"] is False
