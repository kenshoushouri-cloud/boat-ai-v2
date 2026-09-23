# -*- coding: utf-8 -*-
import json
from copy import deepcopy
from pathlib import Path

import pytest

from research.v4_point_count_marginal_revenue import (
    V4PointCountMarginalRevenueError,
    evaluate_point_counts,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "research/evidence/v4_point_count_marginal_revenue_input_20260918_20260919.json"
EXPECTED = ROOT / "research/evidence/v4_point_count_marginal_revenue_result_20260918_20260919.json"


def evidence():
    return json.loads(INPUT.read_text(encoding="utf-8"))


def test_frozen_sep18_sep19_result_reproduces_exactly():
    actual = evaluate_point_counts(evidence())
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert actual == expected


def test_current_formal_corpus_evaluates_only_one_and_two_points():
    result = evaluate_point_counts(evidence())
    one, two, three, four, five = result["strategies"]

    assert one["profit_yen"] == -10
    assert one["roi_percent"] == 99.167
    assert one["hit_races"] == 2
    assert one["max_drawdown_yen"] == 500

    assert two["profit_yen"] == 920
    assert two["roi_percent"] == 138.333
    assert two["hit_races"] == 4
    assert two["max_drawdown_yen"] == 600

    assert two["incremental_point"] == {
        "point_rank": 2,
        "incremental_investment_yen": 1200,
        "incremental_gross_return_yen": 2130,
        "incremental_profit_yen": 930,
        "marginal_roi_percent": 177.5,
        "incremental_hit_races": 2,
        "incremental_hit_rate_percent": 16.667,
    }

    for row in (three, four, five):
        assert row["status"] == "NOT_EVALUABLE_MISSING_PRE_RESULT_RANKS"
        assert row["post_result_reconstruction_allowed"] is False


def test_rank_three_cannot_be_fabricated_by_only_raising_ranking_count():
    bad = evidence()
    bad["days"][0]["ranking_count"] = 3
    with pytest.raises(
        V4PointCountMarginalRevenueError,
        match="ranked_tickets must exactly match ranking_count",
    ):
        evaluate_point_counts(bad)


def test_ranking_evidence_must_be_predeadline():
    bad = evidence()
    bad["days"][0]["ranking_evidence_generated_at"] = (
        "2026-09-18T10:43:00+09:00"
    )
    with pytest.raises(
        V4PointCountMarginalRevenueError,
        match="ranking evidence is not pre-deadline",
    ):
        evaluate_point_counts(bad)


def test_ticket_rankings_must_be_unique():
    bad = evidence()
    race = bad["days"][0]["races"][0]
    race["ranked_tickets"][1] = race["ranked_tickets"][0]
    with pytest.raises(
        V4PointCountMarginalRevenueError,
        match="ranked_tickets must be unique",
    ):
        evaluate_point_counts(bad)


def test_formal_shape_and_stake_cannot_change_for_cost_optimization():
    bad = evidence()
    bad["stake_per_ticket_yen"] = 50
    with pytest.raises(
        V4PointCountMarginalRevenueError,
        match="fixed at 100",
    ):
        evaluate_point_counts(bad)

    bad = evidence()
    bad["days"][0]["races"] = bad["days"][0]["races"][:5]
    with pytest.raises(
        V4PointCountMarginalRevenueError,
        match="exactly 6 formal races",
    ):
        evaluate_point_counts(bad)


def test_max_drawdown_is_chronological_not_daily_rank_order():
    result = evaluate_point_counts(evidence())
    one = result["strategies"][0]
    two = result["strategies"][1]
    assert one["max_drawdown_yen"] == 500
    assert two["max_drawdown_yen"] == 600


def test_module_has_no_io_db_network_or_production_mutation_surface():
    import inspect
    import research.v4_point_count_marginal_revenue as module

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
        "vacuum ",
        "purchase_action=true",
    ):
        assert forbidden not in source
