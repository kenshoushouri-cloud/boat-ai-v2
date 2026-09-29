# -*- coding: utf-8 -*-
from research.monthly_profit_target_feasibility import (
    MonthlyScenario,
    build_reference_report,
    ceil_to_100_jpy,
    evidence_scaling_gate,
    required_roi_for_target,
    required_stake_for_target,
)


def test_required_roi_for_one_to_three_races_at_100_yen():
    values = [
        required_roi_for_target(
            target_profit_jpy=50_000,
            days=30,
            races_per_day=r,
            tickets_per_race=2,
            stake_per_ticket_jpy=100,
        )
        for r in (1, 2, 3)
    ]
    assert round(values[0] * 100, 2) == 933.33
    assert round(values[1] * 100, 2) == 516.67
    assert round(values[2] * 100, 2) == 377.78


def test_v4_current_overall_roi_does_not_reach_monthly_target_at_100_yen():
    s = MonthlyScenario(
        days=30,
        races_per_day=6,
        tickets_per_race=2,
        stake_per_ticket_jpy=100,
        roi=1.477273,
    )
    assert round(s.investment_jpy) == 36_000
    assert round(s.profit_jpy) == 17_182
    assert s.profit_jpy < 50_000


def test_required_stake_returns_none_when_roi_is_not_profitable():
    assert required_stake_for_target(
        target_profit_jpy=50_000,
        days=30,
        races_per_day=2.71,
        tickets_per_race=1,
        roi=0.565625,
    ) is None


def test_scaling_gate_requires_sample_and_conservative_profitability():
    assert evidence_scaling_gate(
        observed_units=8,
        required_units=20,
        conservative_roi=1.123684,
    )["stake_scaling_review_allowed"] is False
    assert evidence_scaling_gate(
        observed_units=20,
        required_units=20,
        conservative_roi=1.123684,
    )["stake_scaling_review_allowed"] is True
    assert evidence_scaling_gate(
        observed_units=100,
        required_units=100,
        conservative_roi=0.99,
    )["stake_scaling_review_allowed"] is False


def test_reference_report_never_authorizes_stake_or_purchase_change():
    r = build_reference_report()
    assert r["policy"]["stake_change_authorized"] is False
    assert r["policy"]["purchase_action"] is False
    assert r["policy"]["production_behavior_changed"] is False
    assert r["v4_formal_top2"]["evidence_gate"]["stake_change_authorized"] is False
    assert r["s03_m2"]["evidence_gate"]["stake_change_authorized"] is False


def test_ceil_to_100_is_planning_only_rounding():
    assert ceil_to_100_jpy(291.01) == 300
    assert ceil_to_100_jpy(None) is None
