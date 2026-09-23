# -*- coding: utf-8 -*-
from pathlib import Path

from research.v4_position_conditional_tail_walkforward_pg import (
    PairwiseLogit,
    SECOND_DIM,
    THIRD_DIM,
    challenger_top2,
    lane_base_feature_map,
    second_features,
    third_features,
)
from research import candidate_discovery_v4_contract as v4


def zero_base():
    return {lane: (0.0,) * 6 for lane in v4.LANES}


def test_feature_dimensions_are_frozen():
    assert SECOND_DIM == 14
    assert THIRD_DIM == 16
    base = zero_base()
    assert len(second_features(base, candidate=2, first=1)) == SECOND_DIM
    assert len(third_features(base, candidate=3, first=1, second=2)) == THIRD_DIM


def test_zero_weight_model_is_deterministic_and_keeps_head_fixed():
    second = PairwiseLogit(SECOND_DIM)
    third = PairwiseLogit(THIRD_DIM)
    top2, p2 = challenger_top2(
        first=3,
        base_features=zero_base(),
        second_model=second,
        third_model=third,
    )
    assert len(top2) == 2
    assert all(ticket.startswith("3-") for ticket in top2)
    assert abs(sum(p2.values()) - 1.0) < 1e-12


def test_pairwise_fit_moves_target_score_up():
    model = PairwiseLogit(2)
    features = {
        1: (1.0, 0.0),
        2: (0.0, 1.0),
        3: (-1.0, 0.0),
    }
    before = model.score(features[1]) - model.score(features[2])
    for _ in range(20):
        model.fit_choice(
            target=1,
            alternatives=(1, 2, 3),
            feature_fn=lambda lane: features[lane],
        )
    after = model.score(features[1]) - model.score(features[2])
    assert after > before


def test_source_freezes_block_weights_and_tickets_before_result():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_position_conditional_tail_walkforward_pg.py"
    ).read_text(encoding="utf-8")
    assert source.index("frozen = current_day_snapshot") < source.index(
        "results = hist.fetch_selected_results"
    )
    assert source.index("evaluate_frozen_day") < source.index("train_block(")
    low = source.lower()
    assert "set transaction read only" in low
    assert "training_uses_prior_blocks_only" in low
    assert "current_predicted_head_fixed" in low
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "purchase_action=true",
    ):
        assert forbidden not in low


def test_workflow_is_non_enumerating():
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/v4-position-conditional-tail-readonly.yml"
    ).read_text(encoding="utf-8").lower()
    assert "secrets.v4_backtest_database_url" in workflow
    assert "secrets.railway_token" in workflow
    assert "railway run" in workflow
    assert "postgres-recovery" in workflow
    assert "".join(("railway", " variable", " list")) not in workflow
    assert "".join(("print", "env")) not in workflow
