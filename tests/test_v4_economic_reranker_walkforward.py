# -*- coding: utf-8 -*-
import copy

from research.v4_economic_reranker_contract import CONTROL_PAIR
from research.v4_economic_reranker_walkforward import (
    evaluate,
    rows_with_blocks,
    select_walkforward_pairs,
    settle_rows,
)


def source():
    blocks = []
    records = []
    # Synthetic structure mirrors 10 chronological blocks, one day/block,
    # six races/day. Counts are patched in tests that call pure helpers only.
    for block in range(1, 11):
        day = f"2026-{block:02d}-01"
        blocks.append(
            {
                "block": block,
                "start_date": day,
                "end_date": day,
                "days": 1,
            }
        )
        for race in range(6):
            actual = "4-5-1" if block <= 2 else "1-2-3"
            records.append(
                {
                    "date": day,
                    "race_id": f"b{block}r{race}",
                    "ranked_top5": [
                        "1-2-3",
                        "1-3-2",
                        "2-1-3",
                        "4-5-1",
                        "5-4-1",
                    ],
                    "actual_trifecta": actual,
                    "payout_yen": 1000,
                }
            )
    return {
        "walkforward_blocks": blocks,
        "evaluated_race_records": records,
    }


def test_rows_map_to_exact_chronological_blocks():
    rows = rows_with_blocks(source())
    assert len(rows) == 60
    assert [rows[i * 6]["block"] for i in range(10)] == list(range(1, 11))


def test_pair_selection_is_global_per_block_and_warmup_is_control():
    rows = rows_with_blocks(source())
    pairs = select_walkforward_pairs(rows)
    assert pairs[1] == CONTROL_PAIR
    assert pairs[2] == CONTROL_PAIR
    # Prior warmup blocks pay only ranks 4/5, so block 3 must not stay control.
    assert pairs[3] == (4, 5)
    assert all(isinstance(pair, tuple) and len(pair) == 2 for pair in pairs.values())


def test_settlement_keeps_exact_same_volume_as_control():
    rows = rows_with_blocks(source())
    selected_pairs = select_walkforward_pairs(rows)
    control_pairs = {block: CONTROL_PAIR for block in range(1, 11)}
    selected = settle_rows(rows, pair_by_block=selected_pairs)
    control = settle_rows(rows, pair_by_block=control_pairs)
    assert selected["races"] == control["races"] == 60
    assert selected["bets"] == control["bets"] == 120
    assert selected["investment_yen"] == control["investment_yen"]


def test_current_block_results_do_not_affect_its_pair():
    data = source()
    rows = rows_with_blocks(data)
    before = select_walkforward_pairs(rows)[3]

    changed = copy.deepcopy(data)
    for row in changed["evaluated_race_records"]:
        if row["date"] == "2026-03-01":
            row["actual_trifecta"] = "5-4-1"
            row["payout_yen"] = 999999
    after = select_walkforward_pairs(rows_with_blocks(changed))[3]
    assert before == after


def test_evaluator_source_has_no_market_or_db_surface():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    text = (
        root / "research/v4_economic_reranker_walkforward.py"
    ).read_text(encoding="utf-8").lower()
    for forbidden in (
        "psycopg",
        "database_url",
        "v2_realtime_odds",
        "market_rank",
        "insert into",
        "update v2_",
        "delete from",
        "purchase_action=true",
    ):
        assert forbidden not in text
