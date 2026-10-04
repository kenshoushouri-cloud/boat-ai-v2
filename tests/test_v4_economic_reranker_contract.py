# -*- coding: utf-8 -*-
from research.v4_economic_reranker_contract import (
    BLOCK_COUNT,
    CONTROL_PAIR,
    PAIR_CANDIDATES,
    WARMUP_BLOCKS,
    choose_pair_for_block,
    contract_metadata,
    freeze_pair,
)


def row(block, actual="1-2-3", payout=1000):
    return {
        "block": block,
        "ranked_top5": [
            "1-2-3",
            "1-3-2",
            "2-1-3",
            "2-3-1",
            "3-1-2",
        ],
        "actual_trifecta": actual,
        "payout_yen": payout,
    }


def test_fixed_pair_family_is_exactly_ten_combinations():
    assert len(PAIR_CANDIDATES) == 10
    assert CONTROL_PAIR == (1, 2)
    assert PAIR_CANDIDATES[0] == (1, 2)
    assert PAIR_CANDIDATES[-1] == (4, 5)


def test_freeze_pair_always_returns_exactly_two_preexisting_top5_tickets():
    tickets = row(1)["ranked_top5"]
    frozen = freeze_pair(tickets, (2, 5))
    assert frozen == (tickets[1], tickets[4])
    assert len(set(frozen)) == 2


def test_first_two_blocks_are_forced_control():
    rows = [row(1, actual="3-1-2", payout=50000)]
    assert WARMUP_BLOCKS == 2
    assert choose_pair_for_block(rows, current_block=1) == CONTROL_PAIR
    assert choose_pair_for_block(rows, current_block=2) == CONTROL_PAIR


def test_current_block_result_cannot_change_pair_choice():
    # Prior blocks favor ranks (4,5).
    prior = []
    for block in (1, 2):
        prior.extend(
            [
                row(block, actual="2-3-1", payout=3000),
                row(block, actual="3-1-2", payout=3000),
            ]
        )
    chosen_without_current = choose_pair_for_block(prior, current_block=3)

    # Add an enormous current-block result for control. The current block must
    # remain invisible to the selector.
    contaminated_input = prior + [
        row(3, actual="1-2-3", payout=99999999),
    ]
    chosen_with_current = choose_pair_for_block(
        contaminated_input,
        current_block=3,
    )
    assert chosen_without_current == (4, 5)
    assert chosen_with_current == chosen_without_current


def test_metadata_locks_volume_and_safety():
    meta = contract_metadata()
    assert meta["core_races_per_day"] == 6
    assert meta["points_per_race"] == 2
    assert meta["candidate_skip_allowed"] is False
    assert meta["race_replacement_allowed"] is False
    assert meta["market_input_allowed"] is False
    assert meta["stake_change_allowed"] is False
    assert meta["purchase_action"] is False
    assert meta["block_count"] == BLOCK_COUNT
