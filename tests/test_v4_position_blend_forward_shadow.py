# -*- coding: utf-8 -*-
from copy import deepcopy

import pytest

from research import candidate_discovery_v4_contract as v4
from research.v4_position_blend_forward_shadow import (
    ALPHA,
    FORWARD_START_DATE,
    SECOND_WEIGHTS,
    THIRD_WEIGHTS,
    blend_distribution,
    first_marginals,
    freeze_payload,
    lane_feature_map,
    learned_distribution,
    settle_payload,
)


def control_distribution():
    raw = {lane: 7.0 - lane * 0.5 for lane in v4.LANES}
    return v4.ticket_probabilities(raw)


def lane_inputs():
    return {
        str(lane): {
            "base_raw": 7.0 - lane * 0.3,
            "national_win_rate": 4.0 + lane * 0.4,
            "national_place2_rate": 25.0 + lane * 2.0,
            "local_place2_rate": 24.0 + lane * 1.5,
            "avg_st": 0.20 - lane * 0.01,
            "motor_place2_rate": 28.0 + lane * 1.2,
        }
        for lane in v4.LANES
    }


def input_payload():
    probs = control_distribution()
    return {
        "contract": "v4_posblend_forward_input_v1",
        "race_date": FORWARD_START_DATE.isoformat(),
        "observed_at": "2026-09-24T08:30:00+09:00",
        "races": [
            {
                "race_id": f"20260924_01_{idx:02d}",
                "control_probs": probs,
                "lanes": lane_inputs(),
            }
            for idx in range(1, 7)
        ],
    }


def official_results(frozen):
    tickets = ["1-2-3", "1-3-2", "2-1-3", "3-1-2", "4-1-2", "5-1-2"]
    return {
        "results": [
            {
                "race_id": row["race_id"],
                "trifecta_ticket": ticket,
                "trifecta_payout_yen": 1000 + idx * 100,
                "result_status": "official",
                "race_status": "official",
            }
            for idx, (row, ticket) in enumerate(zip(frozen["races"], tickets), 1)
        ]
    }


def test_frozen_model_constants_and_alpha():
    assert ALPHA == 0.25
    assert len(SECOND_WEIGHTS) == 14
    assert len(THIRD_WEIGHTS) == 16


def test_learned_and_blend_preserve_current_first_marginal():
    control = control_distribution()
    base = lane_feature_map(lane_inputs())
    learned = learned_distribution(control, base)
    shadow = blend_distribution(control, learned)
    before = first_marginals(control)
    for candidate in (learned, shadow):
        after = first_marginals(candidate)
        for lane in v4.LANES:
            assert abs(before[lane] - after[lane]) < 1e-12


def test_freeze_is_exact_six_and_result_blind():
    frozen = freeze_payload(input_payload())
    assert frozen["phase"] == "PRE_RESULT_FROZEN"
    assert len(frozen["races"]) == 6
    assert frozen["policy"]["purchase_action"] is False
    assert all(len(row["shadow_top2"]) == 2 for row in frozen["races"])

    contaminated = input_payload()
    contaminated["races"][0]["payout_yen"] = 1234
    with pytest.raises(ValueError, match="forbidden field"):
        freeze_payload(contaminated)


def test_freeze_rejects_pre_preregistered_dates_and_five_race_shrink():
    too_old = input_payload()
    too_old["race_date"] = "2026-09-23"
    with pytest.raises(ValueError, match="precedes"):
        freeze_payload(too_old)

    five = input_payload()
    five["races"] = five["races"][:5]
    with pytest.raises(ValueError, match="exactly six"):
        freeze_payload(five)


def test_settlement_uses_frozen_top2_and_exact_official_set():
    frozen = freeze_payload(input_payload())
    settled = settle_payload(frozen, official_results(frozen))
    assert settled["phase"] == "POST_RESULT_SETTLED"
    assert settled["races"] == 6
    assert settled["policy"]["tickets_recomputed_after_result"] is False

    broken = official_results(frozen)
    broken["results"][0]["result_status"] = "provisional"
    with pytest.raises(ValueError, match="official/official"):
        settle_payload(frozen, broken)


def test_settlement_detects_frozen_artifact_tampering():
    frozen = freeze_payload(input_payload())
    tampered = deepcopy(frozen)
    tampered["races"][0]["shadow_top2"] = ["6-5-4", "6-4-5"]
    with pytest.raises(ValueError, match="SHA mismatch"):
        settle_payload(tampered, official_results(frozen))
