# -*- coding: utf-8 -*-
from research.matched_contract_backtest_preflight import (
    build_preflight,
    current_status,
    v4_contract_snapshot,
)
from research.v5_matched_backtest_contract import (
    V5_CANDIDATE_ID,
    shared_time_split_manifest,
    v5_candidate_manifest,
)


def _gates(v4_days=20, s03_n=100, clean=True):
    return {
        "formal_v4_resolved_days": v4_days,
        "s03_m2_officially_evaluated": s03_n,
        "evidence_contract_clean": clean,
    }


def test_current_frozen_contract_fails_closed_only_on_live_checks():
    out = current_status()
    assert out["execution_ready"] is False
    assert out["v5_candidate"]["valid"] is True
    assert out["v5_candidate"]["comparative"] is True
    assert out["time_split"]["valid"] is True
    assert "V5_PROSPECTIVE_GATE_STATE_REQUIRED" in out["blockers"]
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


def test_v5_candidate_is_distinct_but_keeps_formal_two_ticket_contract():
    x = v5_candidate_manifest()
    assert x["candidate_id"] == V5_CANDIDATE_ID
    assert x["base_probability_contract_unchanged"] is True
    assert x["base_structural_selector_unchanged"] is True
    assert x["formal_tickets_per_selected_race"] == 2
    assert x["unit_yen_per_ticket"] == 100
    assert x["investment_yen_per_selected_race"] == 200
    assert x["odds_read_for_selection"] is False
    assert x["expected_value_filter"] is False
    assert x["motor2_overlay"]["ticket_position_weights"] == [1.0, 0.6, 0.3]
    assert x["motor2_overlay"]["ticket_pass_condition"] == "score > 0.0"
    assert x["motor2_overlay"]["race_pass_condition"] == "both frozen V4 TOP2 tickets pass"
    assert x["comparison_delta"]


def test_shared_split_is_prefrozen_and_chronological():
    x = shared_time_split_manifest()
    assert x["frozen_before_backtest_results"] is True
    assert x["no_retune_between_windows"] is True
    assert x["windows"] == [
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
    ]


def test_frozen_contract_can_pass_only_with_gates_and_readiness():
    out = build_preflight(
        v5_candidate_manifest=v5_candidate_manifest(),
        time_split_manifest=shared_time_split_manifest(),
        prospective_gate_state=_gates(),
        live_readiness_passed=True,
    )
    assert out["execution_ready"] is True
    assert out["blockers"] == []
    assert out["prospective_admission"]["valid"] is True
    assert out["safety"]["database_write"] is False
    assert out["safety"]["railway_config_change"] is False
    assert out["safety"]["production_change"] is False
    assert out["safety"]["purchase_action"] is False


def test_v4_20_gate_cannot_be_lowered():
    out = build_preflight(
        v5_candidate_manifest=v5_candidate_manifest(),
        time_split_manifest=shared_time_split_manifest(),
        prospective_gate_state=_gates(v4_days=19),
        live_readiness_passed=True,
    )
    assert out["execution_ready"] is False
    assert "FORMAL_V4_20_NOT_REACHED" in out["blockers"]


def test_s03_100_gate_cannot_be_lowered():
    out = build_preflight(
        v5_candidate_manifest=v5_candidate_manifest(),
        time_split_manifest=shared_time_split_manifest(),
        prospective_gate_state=_gates(s03_n=99),
        live_readiness_passed=True,
    )
    assert out["execution_ready"] is False
    assert "S03_M2_100_NOT_REACHED" in out["blockers"]


def test_clean_evidence_is_mandatory():
    out = build_preflight(
        v5_candidate_manifest=v5_candidate_manifest(),
        time_split_manifest=shared_time_split_manifest(),
        prospective_gate_state=_gates(clean=False),
        live_readiness_passed=True,
    )
    assert out["execution_ready"] is False
    assert "EVIDENCE_CONTRACT_NOT_CLEAN" in out["blockers"]


def test_historical_readiness_remains_separate_from_prospective_gates():
    out = build_preflight(
        v5_candidate_manifest=v5_candidate_manifest(),
        time_split_manifest=shared_time_split_manifest(),
        prospective_gate_state=_gates(),
        live_readiness_passed=False,
    )
    assert out["execution_ready"] is False
    assert "LIVE_READONLY_HISTORICAL_READINESS_PASS_REQUIRED" in out["blockers"]


def test_v5_selector_cannot_read_odds():
    v5 = v5_candidate_manifest()
    v5["odds_read_for_selection"] = True
    out = build_preflight(
        v5_candidate_manifest=v5,
        time_split_manifest=shared_time_split_manifest(),
        prospective_gate_state=_gates(),
        live_readiness_passed=True,
    )
    assert out["execution_ready"] is False
    assert "V5_SELECTOR_MUST_NOT_READ_ODDS" in out["blockers"]
