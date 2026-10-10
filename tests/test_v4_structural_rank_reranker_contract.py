# -*- coding: utf-8 -*-
from research.v4_structural_rank_reranker_contract import (
    CONTEXTS,
    CONTROL_RANKS,
    MIN_CONTEXT_RACES_PER_BLOCK,
    choose_ranks_for_context,
    contract_metadata,
    structural_context,
)


def top5_h1_p1():
    return ["1-2-3", "1-2-4", "1-3-2", "1-4-2", "1-5-2"]


def top5_h1_p0():
    return ["1-2-3", "1-3-2", "1-4-2", "1-5-2", "1-6-2"]


def top5_hm_p1():
    return ["1-2-3", "1-2-4", "2-1-3", "2-3-1", "1-3-2"]


def top5_hm_p0():
    return ["1-2-3", "2-1-3", "1-3-2", "2-3-1", "1-4-2"]


def make_row(block, ranked_top5, actual, payout=1000):
    return {
        "block": block,
        "ranked_top5": ranked_top5,
        "actual_trifecta": actual,
        "payout_yen": payout,
    }


def test_exact_four_broad_contexts():
    assert CONTEXTS == ("H1_P0", "H1_P1", "HM_P0", "HM_P1")
    assert structural_context(top5_h1_p1()) == "H1_P1"
    assert structural_context(top5_h1_p0()) == "H1_P0"
    assert structural_context(top5_hm_p1()) == "HM_P1"
    assert structural_context(top5_hm_p0()) == "HM_P0"


def test_warmup_is_control():
    assert choose_ranks_for_context([], context="H1_P0", current_block=1) == CONTROL_RANKS
    assert choose_ranks_for_context([], context="HM_P1", current_block=2) == CONTROL_RANKS


def test_sparse_context_falls_back_to_control():
    rows = [
        make_row(1, top5_h1_p0(), "1-4-2")
        for _ in range(MIN_CONTEXT_RACES_PER_BLOCK - 1)
    ]
    rows += [
        make_row(2, top5_h1_p0(), "1-4-2")
        for _ in range(MIN_CONTEXT_RACES_PER_BLOCK)
    ]
    assert choose_ranks_for_context(
        rows,
        context="H1_P0",
        current_block=3,
    ) == CONTROL_RANKS


def test_prior_blocks_only_can_select_noncontrol_ranks():
    rows = []
    for block in (1, 2):
        for _ in range(MIN_CONTEXT_RACES_PER_BLOCK):
            rows.append(make_row(block, top5_h1_p0(), "1-4-2", payout=1500))
    chosen = choose_ranks_for_context(
        rows,
        context="H1_P0",
        current_block=3,
    )
    assert chosen == (1, 3)


def test_current_block_outcome_does_not_change_current_choice():
    rows = []
    for block in (1, 2):
        for _ in range(MIN_CONTEXT_RACES_PER_BLOCK):
            rows.append(make_row(block, top5_h1_p0(), "1-4-2", payout=1500))
    before = choose_ranks_for_context(rows, context="H1_P0", current_block=3)

    contaminated = rows + [
        make_row(3, top5_h1_p0(), "1-2-3", payout=999999)
        for _ in range(MIN_CONTEXT_RACES_PER_BLOCK)
    ]
    after = choose_ranks_for_context(
        contaminated,
        context="H1_P0",
        current_block=3,
    )
    assert before == after


def test_metadata_locks_volume_and_excludes_market_gate():
    meta = contract_metadata()
    assert meta["core_races_per_day"] == 6
    assert meta["points_per_race"] == 2
    assert meta["daily_rank_used_for_selection"] is False
    assert meta["market_input_allowed"] is False
    assert meta["odds_gate_allowed"] is False
    assert meta["candidate_skip_allowed"] is False
    assert meta["production_change_allowed"] is False
    assert meta["purchase_action"] is False
