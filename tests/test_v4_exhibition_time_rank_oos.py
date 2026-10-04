# -*- coding: utf-8 -*-
from pathlib import Path

from research.v4_exhibition_time_rank_contract import (
    COEFFICIENT_GRID,
    adjust_base_raw,
    contract_metadata,
)
from research.v4_exhibition_time_rank_oos_pg import (
    aggregate,
    block_for,
    coef_key,
    complete_exhibition_ranks,
    select_coefficients,
    split_blocks,
)


def test_frozen_coefficient_grid_and_null_are_exact():
    assert COEFFICIENT_GRID == (0.0, 0.05, 0.10, 0.20)
    assert coef_key(0.0) == "ex_0.00"
    assert coef_key(0.2) == "ex_0.20"


def test_complete_exhibition_rank_requires_exact_six_permutation():
    good = [
        {"lane": lane, "exhibition_time_rank": lane}
        for lane in range(1, 7)
    ]
    assert complete_exhibition_ranks(good) == {lane: lane for lane in range(1, 7)}
    assert complete_exhibition_ranks(good[:-1]) == {}
    tied = [dict(row) for row in good]
    tied[-1]["exhibition_time_rank"] = 5
    assert complete_exhibition_ranks(tied) == {}


def test_adjustment_is_positive_for_better_rank_and_missing_is_neutral():
    base = {lane: 1.0 for lane in range(1, 7)}
    ranks = {lane: lane for lane in range(1, 7)}
    got = adjust_base_raw(base, ranks, 0.10)
    assert got[1] > got[2] > got[3] > got[4] > got[5] > got[6]
    assert adjust_base_raw(base, {}, 0.20) == base
    assert adjust_base_raw(base, ranks, 0.0) == base


def test_contract_forbids_old_coefficient_reuse_filters_and_production():
    m = contract_metadata()
    assert m["coefficient_grid"] == [0.0, 0.05, 0.10, 0.20]
    assert m["old_v22_or_bao_coefficients_reused"] is False
    assert m["same_block_outcomes_allowed_for_selection"] is False
    assert m["historical_snapshot_is_prospective_timing_proof"] is False
    assert m["positive_result_requires_fresh_forward"] is True
    assert m["odds_used"] is False
    assert m["threshold_search"] is False
    assert m["venue_filter_search"] is False
    assert m["race_band_filter_search"] is False
    assert m["production_change"] is False
    assert m["purchase_action"] is False


def test_coefficient_selection_uses_only_prior_full6_blocks_and_tie_smallest():
    bounds = [
        {"block": 1, "start": "2026-01-01", "end": "2026-01-02", "days": 2},
        {"block": 2, "start": "2026-01-03", "end": "2026-01-04", "days": 2},
        {"block": 3, "start": "2026-01-05", "end": "2026-01-06", "days": 2},
        {"block": 4, "start": "2026-01-07", "end": "2026-01-08", "days": 2},
        {"block": 5, "start": "2026-01-09", "end": "2026-01-10", "days": 2},
        {"block": 6, "start": "2026-01-11", "end": "2026-01-12", "days": 2},
        {"block": 7, "start": "2026-01-13", "end": "2026-01-14", "days": 2},
        {"block": 8, "start": "2026-01-15", "end": "2026-01-16", "days": 2},
        {"block": 9, "start": "2026-01-17", "end": "2026-01-18", "days": 2},
        {"block": 10, "start": "2026-01-19", "end": "2026-01-20", "days": 2},
    ]
    rows = {}
    for coef in COEFFICIENT_GRID:
        key = coef_key(coef)
        rows[key] = [
            {
                "date": "2026-01-01",
                "head_log_loss": 1.0 if coef in (0.05, 0.10) else 1.2,
                "exhibition_lane_count": 6,
            },
            {
                "date": "2026-01-03",
                "head_log_loss": 1.0 if coef in (0.05, 0.10) else 1.2,
                "exhibition_lane_count": 6,
            },
        ]
    selected = select_coefficients(rows, bounds)
    assert selected[3]["coefficient"] == 0.05


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


def test_block_split_and_clamp_are_deterministic():
    days = [f"2026-01-{x:02d}" for x in range(1, 11)]
    assert [len(x) for x in split_blocks(days, 3)] == [4, 3, 3]
    bounds = [
        {"block": 1, "start": "2026-01-01", "end": "2026-01-03", "days": 3},
        {"block": 2, "start": "2026-01-04", "end": "2026-01-06", "days": 3},
    ]
    assert block_for("2026-01-02", bounds) == 1
    assert block_for("2026-01-07", bounds) == 2


def test_replay_is_read_only_freezes_all_candidates_before_results_and_has_no_odds():
    root = Path(__file__).resolve().parents[1]
    src = (root / "research" / "v4_exhibition_time_rank_oos_pg.py").read_text(
        encoding="utf-8"
    )
    low = src.lower()
    assert "set transaction read only" in low
    assert src.index("prepared = prepare_day(helper, cur, day)") < src.index(
        "results = helper.fetch_selected_results(cur, day, union_ids)"
    )
    assert "for key in keys" in src[src.index("union_ids = sorted"):src.index(
        "results = helper.fetch_selected_results(cur, day, union_ids)"
    )]
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "purchase_action=true",
        "v2_odds",
        "send_line",
    ):
        assert forbidden not in low
