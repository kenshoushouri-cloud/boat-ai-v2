# -*- coding: utf-8 -*-
from research.matched_contract_backtest_preflight import (
    TIME_SPLIT_CONTRACT,
    V5_SPEC_CONTRACT,
    build_preflight,
    v4_contract_snapshot,
)


def _split():
    return {
        "contract": TIME_SPLIT_CONTRACT,
        "frozen_before_backtest_results": True,
        "windows": [
            {
                "name": "TRAIN",
                "start_date": "2025-07-01",
                "end_date": "2026-03-31",
            },
            {
                "name": "VALID",
                "start_date": "2026-04-01",
                "end_date": "2026-05-31",
            },
            {
                "name": "OOS",
                "start_date": "2026-06-01",
                "end_date": "2026-09-30",
            },
        ],
    }


def _v5(delta):
    return {
        "contract": V5_SPEC_CONTRACT,
        "candidate_id": "v5-research-candidate-test",
        "frozen_before_backtest_results": True,
        "production_activation_allowed": False,
        "odds_read_for_selection": False,
        "expected_value_filter": False,
        "comparison_delta": delta,
    }


def test_current_state_is_blocked_until_v5_split_and_live_readiness_are_frozen():
    out = build_preflight()
    assert out["execution_ready"] is False
    assert "V5_CANDIDATE_SPEC_NOT_FROZEN" in out["blockers"]
    assert "TIME_SPLIT_NOT_FROZEN" in out["blockers"]
    assert "LIVE_READONLY_HISTORICAL_READINESS_PASS_REQUIRED" in out["blockers"]


def test_v4_snapshot_is_bound_to_current_executable_contract():
    x = v4_contract_snapshot()
    assert x["course_coefficient"] == 0.50
    assert x["opponent_pressure_coefficient"] == 1.0
    assert x["opponent_pressure_role"] == "first_place_only"
    assert x["motor2_beta"] == 0.06
    assert x["probability_temperature"] == 2.20
    assert x["selector_signals"] == [
        "head_p1",
        "head_margin",
        "top3_mass",
        "concentration",
    ]
    assert x["formal_races"] == 6
    assert x["formal_tickets_per_race"] == 2
    assert x["odds_read_for_selection"] is False
    assert x["expected_value_filter"] is False


def test_identical_v5_is_not_allowed_to_claim_comparative_backtest():
    out = build_preflight(
        v5_candidate_manifest=_v5([]),
        time_split_manifest=_split(),
        live_readiness_passed=True,
    )
    assert out["execution_ready"] is False
    assert out["v5_candidate"]["valid"] is True
    assert out["v5_candidate"]["comparative"] is False
    assert "V5_NOT_COMPARATIVELY_DISTINCT_FROM_V4" in out["blockers"]


def test_prefrozen_distinct_v5_shared_split_and_readiness_can_pass_preflight():
    out = build_preflight(
        v5_candidate_manifest=_v5(["example_predeclared_research_delta"]),
        time_split_manifest=_split(),
        live_readiness_passed=True,
    )
    assert out["execution_ready"] is True
    assert out["blockers"] == []
    assert out["v5_candidate"]["comparative"] is True
    assert out["time_split"]["valid"] is True
    assert out["safety"]["database_write"] is False
    assert out["safety"]["railway_config_change"] is False
    assert out["safety"]["production_change"] is False
    assert out["safety"]["purchase_action"] is False


def test_split_after_reconstructed_history_is_blocked():
    split = _split()
    split["windows"][-1]["end_date"] = "2026-10-01"
    out = build_preflight(
        v5_candidate_manifest=_v5(["delta"]),
        time_split_manifest=split,
        live_readiness_passed=True,
    )
    assert out["execution_ready"] is False
    assert "TIME_SPLIT_AFTER_RECONSTRUCTED_HISTORY" in out["blockers"]


def test_v5_selector_cannot_read_odds():
    v5 = _v5(["delta"])
    v5["odds_read_for_selection"] = True
    out = build_preflight(
        v5_candidate_manifest=v5,
        time_split_manifest=_split(),
        live_readiness_passed=True,
    )
    assert out["execution_ready"] is False
    assert "V5_SELECTOR_MUST_NOT_READ_ODDS" in out["blockers"]
