# -*- coding: utf-8 -*-
from pathlib import Path

from research import candidate_discovery_v4_contract as v4
from research.v4_input_ablation_replay_pg import (
    EXPECTED_CONTROL_DAYS,
    aggregate,
    block_for_date,
    canonical_block_bounds,
    first_place_marginal,
    max_drawdown,
    prediction_record,
    split_blocks,
)


def test_first_place_marginal_and_prediction_metrics_are_multiclass():
    probs = v4.pl_trifecta({1: 0.40, 2: 0.20, 3: 0.15, 4: 0.10, 5: 0.08, 6: 0.07})
    marginal = first_place_marginal(probs)
    assert abs(sum(marginal.values()) - 1.0) < 1e-12
    assert max(marginal, key=marginal.get) == 1

    row = prediction_record(
        day=__import__("datetime").date(2026, 1, 1),
        variant="control",
        race_id="r1",
        probs=probs,
        actual_ticket="1-2-3",
        payout_yen=1000,
        selected_top6=["r1", "r2", "r3", "r4", "r5", "r6"],
        meta={"course_lane_count": 6, "opponent_available": True, "motor_available": True},
    )
    assert row["head_correct"] is True
    assert row["head_log_loss"] > 0
    assert 0 <= row["head_brier"] <= 2


def test_aggregate_keeps_proper_scores_and_economics_separate():
    rows = [
        {
            "date": "2026-01-01",
            "head_correct": True,
            "head_log_loss": 0.2,
            "head_brier": 0.1,
            "top2_hit": True,
            "investment_yen": 200,
            "gross_return_yen": 500,
            "profit_yen": 300,
            "course_lane_count": 6,
            "opponent_available": True,
            "motor_available": True,
        },
        {
            "date": "2026-01-02",
            "head_correct": False,
            "head_log_loss": 1.2,
            "head_brier": 0.8,
            "top2_hit": False,
            "investment_yen": 200,
            "gross_return_yen": 0,
            "profit_yen": -200,
            "course_lane_count": 0,
            "opponent_available": False,
            "motor_available": True,
        },
    ]
    got = aggregate(rows)
    assert got["top1_head_accuracy_percent"] == 50.0
    assert got["head_log_loss"] == 0.7
    assert got["head_brier"] == 0.45
    assert got["formal_top2_hit_rate_percent"] == 50.0
    assert got["profit_yen"] == 100
    assert got["roi_percent"] == 125.0
    assert got["profitable_day_rate_percent"] == 50.0


def test_chronological_blocks_are_deterministic():
    days = [f"2026-01-{i:02d}" for i in range(1, 11)]
    groups = split_blocks(days, 3)
    assert [len(x) for x in groups] == [4, 3, 3]
    bounds = canonical_block_bounds(days)
    assert len(bounds) == 10
    assert block_for_date("2026-01-01", bounds) == 1
    assert block_for_date("2026-01-10", bounds) == 10


def test_drawdown_and_control_day_guard_are_fixed():
    assert max_drawdown([100, -50, -100, 200, -20]) == 150
    assert EXPECTED_CONTROL_DAYS == 432


def test_replay_source_is_read_only_and_result_access_is_after_freeze():
    root = Path(__file__).resolve().parents[1]
    src = (root / "research/v4_input_ablation_replay_pg.py").read_text(encoding="utf-8")
    low = src.lower()
    assert "set transaction read only" in low
    assert src.index("prepared = prepare_day(helper, cur, day)") < src.index(
        "results = helper.fetch_selected_results(cur, day, frozen_union)"
    )
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "purchase_action=true",
        "v2_odds",
    ):
        assert forbidden not in low


def test_replay_workflow_is_one_shot_non_enumerating_and_pinned():
    root = Path(__file__).resolve().parents[1]
    wf = (root / ".github/workflows/v4-input-ablation-replay-readonly.yml").read_text(
        encoding="utf-8"
    ).lower()
    assert "research/.v4-input-ablation-run-once-20260925" in wf
    assert "ac91c9a2e9570d3af3589e2e98b6529a77c14756" in wf
    assert "postgres-recovery" in wf
    assert "railway run" in wf
    for forbidden in ("railway variable list", "printenv", "env |", "railway-vars.json"):
        assert forbidden not in wf
