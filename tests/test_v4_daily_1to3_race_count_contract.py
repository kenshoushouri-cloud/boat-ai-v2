# -*- coding: utf-8 -*-
from research.v4_daily_1to3_race_count_contract import (
    POINTS_PER_RACE,
    RACE_COUNT_CANDIDATES,
    WARMUP_RACE_COUNT,
    _daily_rows,
    block_metrics,
    choose_race_count_for_block,
    contract_metadata,
)


def make_day(day, block, payouts):
    rows = []
    for rank in range(1, 7):
        actual = "1-2-3"
        ranked = ["1-2-3", "1-3-2", "2-1-3", "2-3-1", "3-1-2"]
        payout = payouts.get(rank, 1000)
        if payout is None:
            actual = "6-5-4"
            payout = 1000
        rows.append(
            {
                "date": day,
                "block": block,
                "race_id": f"{day}-{rank}",
                "daily_rank": rank,
                "ranked_top5": ranked,
                "actual_trifecta": actual,
                "payout_yen": payout,
            }
        )
    return rows


def test_daily_selection_keeps_only_top_k_frozen_ranks():
    rows = make_day("2026-01-01", 1, {})
    assert [r["daily_rank"] for r in _daily_rows(rows, 1)] == [1]
    assert [r["daily_rank"] for r in _daily_rows(rows, 2)] == [1, 2]
    assert [r["daily_rank"] for r in _daily_rows(rows, 3)] == [1, 2, 3]


def test_positive_day_requires_strict_daily_profit():
    rows = make_day(
        "2026-01-01",
        1,
        {1: 300, 2: None, 3: None, 4: None, 5: None, 6: None},
    )
    m1 = block_metrics(rows, race_count=1)
    assert m1["positive_day_rate_percent"] == 100.0
    assert m1["profit_yen"] == 100.0

    rows2 = make_day(
        "2026-01-02",
        1,
        {1: 200, 2: None, 3: None, 4: None, 5: None, 6: None},
    )
    m2 = block_metrics(rows2, race_count=1)
    assert m2["positive_day_rate_percent"] == 0.0
    assert m2["profit_yen"] == 0.0


def test_warmup_count_is_three():
    assert WARMUP_RACE_COUNT == 3
    assert choose_race_count_for_block([], current_block=1) == 3
    assert choose_race_count_for_block([], current_block=2) == 3


def test_current_block_results_cannot_change_current_block_choice():
    prior = []
    for block in (1, 2):
        prior += make_day(
            f"2026-0{block}-01",
            block,
            {1: 600, 2: None, 3: None, 4: None, 5: None, 6: None},
        )
    before = choose_race_count_for_block(prior, current_block=3)

    contaminated = prior + make_day(
        "2026-03-01",
        3,
        {1: None, 2: 999999, 3: 999999, 4: None, 5: None, 6: None},
    )
    after = choose_race_count_for_block(contaminated, current_block=3)
    assert before == after


def test_contract_locks_low_freedom_scope():
    meta = contract_metadata()
    assert meta["race_count_candidates"] == list(RACE_COUNT_CANDIDATES)
    assert meta["points_per_race"] == POINTS_PER_RACE == 2
    assert meta["zero_race_day_allowed"] is False
    assert meta["more_than_three_races_allowed"] is False
    assert meta["ticket_rerank_allowed"] is False
    assert meta["market_input_allowed"] is False
    assert meta["odds_gate_allowed"] is False
    assert meta["production_change_allowed"] is False
    assert meta["purchase_action"] is False
