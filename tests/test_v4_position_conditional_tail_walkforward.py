# -*- coding: utf-8 -*-
from pathlib import Path

from research.v4_position_conditional_tail_walkforward_pg import (
    PairwiseLogit,
    SECOND_DIM,
    THIRD_DIM,
    challenger_distribution,
    first_marginals,
    second_features,
    third_features,
)
from research import candidate_discovery_v4_contract as v4


def zero_base():
    return {lane: (0.0,) * 6 for lane in v4.LANES}


def synthetic_control():
    raw = {lane: 7.0 - lane for lane in v4.LANES}
    return v4.ticket_probabilities(raw)


def test_feature_dimensions_are_frozen():
    assert SECOND_DIM == 14
    assert THIRD_DIM == 16
    base = zero_base()
    assert len(second_features(base, candidate=2, first=1)) == SECOND_DIM
    assert len(third_features(base, candidate=3, first=1, second=2)) == THIRD_DIM


def test_zero_weight_challenger_preserves_every_first_place_marginal():
    second = PairwiseLogit(SECOND_DIM)
    third = PairwiseLogit(THIRD_DIM)
    control = synthetic_control()
    challenger, p2 = challenger_distribution(
        control_probs=control,
        base_features=zero_base(),
        second_model=second,
        third_model=third,
    )
    before = first_marginals(control)
    after = first_marginals(challenger)
    assert len(challenger) == 120
    assert abs(sum(challenger.values()) - 1.0) < 1e-12
    assert set(p2) == set(v4.LANES)
    for lane in v4.LANES:
        assert abs(before[lane] - after[lane]) < 1e-12


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


def test_position_conditional_model_does_not_assume_control_top2_same_head():
    control = synthetic_control()
    # Deliberately replace two top tickets so they may carry different heads.
    ranked = sorted(control.items(), key=lambda kv: (-kv[1], kv[0]))
    assert len(ranked) == 120
    second = PairwiseLogit(SECOND_DIM)
    third = PairwiseLogit(THIRD_DIM)
    challenger, _ = challenger_distribution(
        control_probs=control,
        base_features=zero_base(),
        second_model=second,
        third_model=third,
    )
    assert len(v4.top_tickets(challenger, 2)) == 2


def test_source_freezes_block_outputs_before_result_and_trains_after_block():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_position_conditional_tail_walkforward_pg.py"
    ).read_text(encoding="utf-8")
    assert source.index("frozen = current_day_snapshot") < source.index(
        "results = hist.fetch_selected_results"
    )
    main_source = source[source.index("def main()") :]
    assert main_source.index("evaluate_frozen_day(") < main_source.index("train_block(")
    low = source.lower()
    assert "set transaction read only" in low
    assert "training_uses_prior_blocks_only" in low
    assert "first_place_marginal_preserved" in low
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


def test_main_sorts_set_blocks_before_indexing_dates():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_position_conditional_tail_walkforward_pg.py"
    ).read_text(encoding="utf-8")
    assert "for block_index, block_day_set in enumerate(calendar_blocks, 1):" in source
    assert "block_days = sorted(block_day_set)" in source
    assert source.index("block_days = sorted(block_day_set)") < source.index(
        '"start_date": block_days[0]'
    )
