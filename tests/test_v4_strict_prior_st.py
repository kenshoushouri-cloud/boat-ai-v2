# -*- coding: utf-8 -*-
from datetime import date
from pathlib import Path

from research.v4_strict_prior_st_contract import (
    FAST_BONUS,
    FAST_THRESHOLD,
    SLOW_PENALTY,
    SLOW_THRESHOLD,
    adjust_base_raw,
    contract_metadata,
    prior_st_adjustment,
)
from research.v4_strict_prior_st_replay_pg import (
    aggregate,
    block_for,
    latest_prior_st,
    split_blocks,
)


def test_frozen_previous_st_rule_is_exact():
    assert FAST_THRESHOLD == 0.08
    assert FAST_BONUS == 0.08
    assert SLOW_THRESHOLD == 0.18
    assert SLOW_PENALTY == 0.18
    assert prior_st_adjustment(0.08) == 0.08
    assert prior_st_adjustment(0.09) == 0.0
    assert prior_st_adjustment(0.17) == 0.0
    assert prior_st_adjustment(0.18) == -0.18
    assert prior_st_adjustment(None) == 0.0


def test_adjustment_is_lane_local_and_missing_neutral():
    base = {lane: float(lane) for lane in range(1, 7)}
    got = adjust_base_raw(base, {1: 0.07, 6: 0.20})
    assert got[1] == 1.08
    assert got[6] == 5.82
    assert got[2] == 2.0
    assert got[5] == 5.0


def test_latest_prior_st_excludes_same_day_even_when_present():
    keys = {
        1001: [
            (date(2026, 1, 1), 2, "a"),
            (date(2026, 1, 2), 1, "b"),
            (date(2026, 1, 2), 5, "c"),
        ]
    }
    vals = {1001: [0.11, 0.05, 0.07]}
    assert latest_prior_st(1001, date(2026, 1, 2), keys, vals) == 0.11
    assert latest_prior_st(1001, date(2026, 1, 3), keys, vals) == 0.07


def test_contract_forbids_retune_odds_and_production():
    m = contract_metadata()
    assert m["same_day_results_allowed"] is False
    assert m["threshold_search"] is False
    assert m["coefficient_retune"] is False
    assert m["odds_used"] is False
    assert m["ev_used"] is False
    assert m["result_query_after_both_variant_freezes"] is True
    assert m["production_change"] is False
    assert m["purchase_action"] is False


def test_aggregate_keeps_prediction_and_economics_separate():
    rows = [
        {
            "head_correct": True,
            "head_log_loss": 0.2,
            "head_brier": 0.1,
            "formal_top2_hit": True,
            "investment_yen": 200,
            "gross_return_yen": 500,
            "profit_yen": 300,
        },
        {
            "head_correct": False,
            "head_log_loss": 1.2,
            "head_brier": 0.8,
            "formal_top2_hit": False,
            "investment_yen": 200,
            "gross_return_yen": 0,
            "profit_yen": -200,
        },
    ]
    got = aggregate(rows)
    assert got["head_accuracy_percent"] == 50.0
    assert got["head_log_loss"] == 0.7
    assert got["head_brier"] == 0.45
    assert got["profit_yen"] == 100


def test_block_split_is_deterministic():
    days = [f"2026-01-{x:02d}" for x in range(1, 11)]
    assert [len(x) for x in split_blocks(days, 3)] == [4, 3, 3]


def test_variant_only_date_after_last_control_day_uses_final_canonical_block():
    bounds = [
        {"block": 1, "start": "2026-01-01", "end": "2026-01-03", "days": 3},
        {"block": 2, "start": "2026-01-04", "end": "2026-01-06", "days": 3},
    ]
    assert block_for("2026-01-02", bounds) == 1
    assert block_for("2026-01-06", bounds) == 2
    assert block_for("2026-01-07", bounds) == 2


def test_replay_source_is_read_only_result_after_freeze_and_no_odds():
    root = Path(__file__).resolve().parents[1]
    src = (root / "research" / "v4_strict_prior_st_replay_pg.py").read_text(encoding="utf-8")
    low = src.lower()
    assert "set transaction read only" in low
    assert src.index("prepared = prepare_day(") < src.index(
        "results = helper.fetch_selected_results("
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
