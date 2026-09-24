# -*- coding: utf-8 -*-
from research.v4_daily_one_race_selector_contract import (
    CONTEXTS,
    DAILY_CANDIDATES,
    MIN_CONTEXT_RACES_PER_BLOCK,
    choose_one_race,
    contract_metadata,
    structural_context,
)


def ranked_h1_p0():
    return ["1-2-3", "1-3-2", "1-4-2", "1-5-2", "1-6-2"]


def ranked_h1_p1():
    return ["1-2-3", "1-2-4", "1-3-2", "1-4-2", "1-5-2"]


def ranked_hm_p0():
    return ["1-2-3", "2-1-3", "1-3-2", "2-3-1", "1-4-2"]


def ranked_hm_p1():
    return ["1-2-3", "1-2-4", "2-1-3", "2-3-1", "1-3-2"]


def race(block, day, rank, ranked, actual="6-5-4", payout=1000, score=0.5):
    return {
        "block": block,
        "date": day,
        "race_id": f"{day}-{rank}",
        "daily_rank": rank,
        "race_score": score,
        "ranked_top5": ranked,
        "actual_trifecta": actual,
        "payout_yen": payout,
    }


def day(block, day_text, contexts):
    ranked_map = {
        "H1_P0": ranked_h1_p0(),
        "H1_P1": ranked_h1_p1(),
        "HM_P0": ranked_hm_p0(),
        "HM_P1": ranked_hm_p1(),
    }
    return [
        race(
            block,
            day_text,
            idx + 1,
            ranked_map[context],
            score=1.0 - idx * 0.1,
        )
        for idx, context in enumerate(contexts)
    ]


def test_four_structural_contexts_only():
    assert CONTEXTS == ("H1_P0", "H1_P1", "HM_P0", "HM_P1")
    assert structural_context(ranked_h1_p0()) == "H1_P0"
    assert structural_context(ranked_h1_p1()) == "H1_P1"
    assert structural_context(ranked_hm_p0()) == "HM_P0"
    assert structural_context(ranked_hm_p1()) == "HM_P1"


def test_warmup_uses_daily_rank_one():
    rows = day(1, "2026-01-01", ["HM_P0", "H1_P0", "H1_P1", "HM_P1", "H1_P0", "HM_P0"])
    chosen = choose_one_race([], day_rows=rows, current_block=1)
    assert chosen["daily_rank"] == 1


def test_sparse_history_fails_closed_to_daily_rank_one():
    history = [
        race(1, f"2026-01-{i+1:02d}", 1, ranked_hm_p0(), actual="1-2-3")
        for i in range(MIN_CONTEXT_RACES_PER_BLOCK - 1)
    ]
    rows = day(3, "2026-03-01", ["H1_P0", "HM_P0", "H1_P1", "HM_P1", "H1_P0", "HM_P0"])
    chosen = choose_one_race(history, day_rows=rows, current_block=3)
    assert chosen["daily_rank"] == 1


def test_prior_context_economics_can_choose_non_rank_one():
    history = []
    for block in (1, 2):
        for i in range(MIN_CONTEXT_RACES_PER_BLOCK):
            history.append(
                race(
                    block,
                    f"2026-0{block}-{i+1:02d}",
                    1,
                    ranked_hm_p0(),
                    actual="1-2-3",
                    payout=1200,
                )
            )
            history.append(
                race(
                    block,
                    f"2026-0{block}-{i+1:02d}x",
                    1,
                    ranked_h1_p0(),
                    actual="6-5-4",
                    payout=1200,
                )
            )

    rows = day(3, "2026-03-01", ["H1_P0", "HM_P0", "H1_P1", "HM_P1", "H1_P0", "HM_P0"])
    chosen = choose_one_race(history, day_rows=rows, current_block=3)
    assert chosen["daily_rank"] == 2
    assert structural_context(chosen["ranked_top5"]) == "HM_P0"


def test_current_block_outcomes_cannot_change_current_choice():
    history = []
    for block in (1, 2):
        for i in range(MIN_CONTEXT_RACES_PER_BLOCK):
            history.append(
                race(
                    block,
                    f"2026-0{block}-{i+1:02d}",
                    1,
                    ranked_hm_p0(),
                    actual="1-2-3",
                    payout=1200,
                )
            )

    rows = day(3, "2026-03-01", ["H1_P0", "HM_P0", "H1_P1", "HM_P1", "H1_P0", "HM_P0"])
    before = choose_one_race(history, day_rows=rows, current_block=3)["race_id"]

    contaminated = history + [
        race(3, "2026-03-01", 1, ranked_h1_p0(), actual="1-2-3", payout=999999)
        for _ in range(MIN_CONTEXT_RACES_PER_BLOCK)
    ]
    after = choose_one_race(contaminated, day_rows=rows, current_block=3)["race_id"]
    assert before == after


def test_metadata_locks_exactly_one_race_and_no_odds():
    meta = contract_metadata()
    assert meta["daily_candidates"] == DAILY_CANDIDATES == 6
    assert meta["selected_races_per_day"] == 1
    assert meta["points_per_race"] == 2
    assert meta["zero_race_day_allowed"] is False
    assert meta["more_than_one_race_allowed"] is False
    assert meta["ticket_rerank_allowed"] is False
    assert meta["market_input_allowed"] is False
    assert meta["odds_gate_allowed"] is False
    assert meta["same_day_result_feedback_allowed"] is False
    assert meta["production_change_allowed"] is False
    assert meta["purchase_action"] is False
