# -*- coding: utf-8 -*-
from research.v4_structural_conditional_reranker_contract import (
    CONTROL_PAIR,
    MIN_PRIOR_RACES_PER_STATE,
    PAIR_CANDIDATES,
    choose_pair_for_state,
    contract_metadata,
    structural_state,
)


def make_row(block, daily_rank, tickets, actual, payout=1000):
    return {
        "block": block,
        "daily_rank": daily_rank,
        "ranked_top5": tickets,
        "actual_trifecta": actual,
        "payout_yen": payout,
    }


SINGLE = ["1-2-3", "1-3-2", "1-4-2", "1-2-4", "1-5-2"]
MULTI = ["1-2-3", "1-3-2", "2-1-3", "2-3-1", "3-1-2"]


def test_structural_state_uses_only_daily_rank_and_top5_head_diversity():
    assert structural_state(make_row(1, 1, SINGLE, "1-2-3")) == (
        "high",
        "single_head",
    )
    assert structural_state(make_row(1, 4, MULTI, "1-2-3")) == (
        "mid",
        "multi_head",
    )
    assert structural_state(make_row(1, 6, MULTI, "1-2-3")) == (
        "low",
        "multi_head",
    )


def test_pair_family_always_retains_rank2_and_never_changes_ticket_count():
    assert PAIR_CANDIDATES == ((1, 2), (2, 3), (2, 4), (2, 5))
    assert all(2 in pair and len(pair) == 2 for pair in PAIR_CANDIDATES)


def test_sparse_state_fails_closed_to_control():
    rows = [
        make_row(1, 1, MULTI, "2-1-3")
        for _ in range(MIN_PRIOR_RACES_PER_STATE - 1)
    ]
    assert choose_pair_for_state(
        rows,
        state=("high", "multi_head"),
        current_block=3,
    ) == CONTROL_PAIR


def test_current_block_results_are_invisible():
    rows = []
    for block in (1, 2):
        for _ in range(25):
            rows.append(make_row(block, 1, MULTI, "2-1-3", 1000))

    before = choose_pair_for_state(
        rows,
        state=("high", "multi_head"),
        current_block=3,
    )
    rows.extend(
        make_row(3, 1, MULTI, "1-2-3", 999999)
        for _ in range(20)
    )
    after = choose_pair_for_state(
        rows,
        state=("high", "multi_head"),
        current_block=3,
    )
    assert before == after


def test_switch_requires_both_median_and_cumulative_improvement():
    rows = []
    # In both prior blocks rank3 hits and control does not, so (2,3) should pass.
    for block in (1, 2):
        for _ in range(25):
            rows.append(make_row(block, 1, MULTI, "2-1-3", 1000))
    assert choose_pair_for_state(
        rows,
        state=("high", "multi_head"),
        current_block=3,
    ) == (2, 3)


def test_metadata_locks_volume_and_excludes_odds_filters():
    meta = contract_metadata()
    assert meta["core_races_per_day"] == 6
    assert meta["points_per_race"] == 2
    assert meta["rank2_always_retained"] is True
    assert meta["candidate_skip_allowed"] is False
    assert meta["odds_input_allowed"] is False
    assert meta["venue_filter_allowed"] is False
    assert meta["race_number_filter_allowed"] is False
    assert meta["purchase_action"] is False
