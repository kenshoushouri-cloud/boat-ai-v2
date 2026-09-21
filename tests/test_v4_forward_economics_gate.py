# -*- coding: utf-8 -*-
from copy import deepcopy

import pytest

from research.v4_forward_economics_gate import (
    V4ForwardEconomicsError,
    evaluate_economics,
)


def evidence():
    return {
        "contract": "v4_forward_economics_evidence_v1",
        "period": {
            "start_date": "2026-09-18",
            "end_date": "2026-09-19",
            "operating_cost_yen": 0,
        },
        "policy_guards": {
            "purchase_action": False,
            "threshold_changed_for_cost": False,
            "stake_changed_for_cost": False,
            "candidate_count_changed_for_cost": False,
            "result_after_reconstruction": False,
        },
        "formal_days": [
            {
                "date": "2026-09-18",
                "core_races": 6,
                "core_tickets": 12,
                "exact_hit_races": 2,
                "head_hit_races": 4,
                "first_second_prefix_hit_races": 2,
                "third_only_miss_races": 0,
                "investment_yen": 1200,
                "gross_return_yen": 1100,
                "profit_yen": -100,
            },
            {
                "date": "2026-09-19",
                "core_races": 6,
                "core_tickets": 12,
                "exact_hit_races": 2,
                "head_hit_races": 3,
                "first_second_prefix_hit_races": 3,
                "third_only_miss_races": 1,
                "investment_yen": 1200,
                "gross_return_yen": 2220,
                "profit_yen": 1020,
            },
        ],
    }


def test_current_formal_corpus_reconciles_but_remains_pre30():
    result = evaluate_economics(evidence())
    summary = result["summary"]
    assert summary["core_races"] == 12
    assert summary["core_tickets"] == 24
    assert summary["investment_yen"] == 2400
    assert summary["gross_return_yen"] == 3320
    assert summary["profit_yen"] == 920
    assert summary["roi_percent"] == 138.333
    assert summary["max_cumulative_drawdown_yen"] == 100
    assert result["project_milestones_redefined"] is False
    assert result["milestone_context_required_separately"] is True
    assert result["automatic_plan_change_allowed"] is False
    assert result["human_review_required"] is True


def test_period_operating_cost_is_reported_without_extrapolation():
    data = evidence()
    data["period"]["operating_cost_yen"] = 1000
    result = evaluate_economics(data)
    assert result["summary"]["net_after_period_operating_cost_yen"] == -80
    assert result["summary"]["observed_net_positive"] is False
    assert result["project_milestones_redefined"] is False


@pytest.mark.parametrize(
    "field",
    [
        "purchase_action",
        "threshold_changed_for_cost",
        "stake_changed_for_cost",
        "candidate_count_changed_for_cost",
        "result_after_reconstruction",
    ],
)
def test_cost_pressure_cannot_change_safety_or_prediction_policy(field):
    bad = evidence()
    bad["policy_guards"][field] = True
    with pytest.raises(V4ForwardEconomicsError, match=field):
        evaluate_economics(bad)


def test_profit_must_reconcile_exactly():
    bad = evidence()
    bad["formal_days"][0]["profit_yen"] = 0
    with pytest.raises(V4ForwardEconomicsError, match="does not reconcile"):
        evaluate_economics(bad)


def test_two_ticket_formal_core_shape_is_required():
    bad = evidence()
    bad["formal_days"][0]["core_tickets"] = 11
    with pytest.raises(V4ForwardEconomicsError, match="two tickets per race"):
        evaluate_economics(bad)


def test_economics_gate_does_not_redefine_project_case_milestones():
    data = evidence()
    result = evaluate_economics(data)
    assert result["summary"]["core_races"] == 12
    assert result["project_milestones_redefined"] is False
    assert result["milestone_context_required_separately"] is True
    assert result["automatic_plan_change_allowed"] is False

def test_module_is_pure_and_has_no_production_or_purchase_surface():
    import inspect
    import research.v4_forward_economics_gate as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "psycopg",
        "database_url",
        "requests",
        "urllib",
        "railway",
        "line_notify",
        "subprocess",
        "os.environ",
        "insert into",
        "update v2_",
        "delete from",
        "vacuum",
    ):
        assert forbidden not in source
