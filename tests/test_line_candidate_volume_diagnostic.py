# -*- coding: utf-8 -*-
from research.line_candidate_volume_diagnostic import (
    _date_range,
    classify_low_core_near_miss,
)


def _row(prob_rank, market_rank, odds):
    return {
        "prob_rank": prob_rank,
        "market_rank": market_rank,
        "odds": odds,
    }


def test_exact_frozen_low_core_boundaries():
    flags = classify_low_core_near_miss([
        _row(11, 1, 3.0),
        _row(20, 1, 4.999),
    ])
    assert flags == {"core_match"}


def test_odds_five_is_not_core_and_is_high_only_near_miss():
    flags = classify_low_core_near_miss([_row(15, 1, 5.0)])
    assert flags == {"odds_high_only"}


def test_probability_rank_only_near_miss():
    flags = classify_low_core_near_miss([_row(10, 1, 4.0)])
    assert flags == {"prob_rank_only"}


def test_market_rank_only_near_miss():
    flags = classify_low_core_near_miss([_row(15, 2, 4.0)])
    assert flags == {"market_rank_only"}


def test_multi_miss_is_used_when_no_single_dimension_near_miss_exists():
    flags = classify_low_core_near_miss([_row(5, 7, 20.0)])
    assert flags == {"multi_miss"}


def test_race_flags_are_nonexclusive_across_tickets():
    flags = classify_low_core_near_miss([
        _row(10, 1, 4.0),
        _row(15, 2, 4.0),
        _row(15, 1, 5.5),
    ])
    assert flags == {
        "prob_rank_only",
        "market_rank_only",
        "odds_high_only",
    }


def test_date_range_is_inclusive():
    assert _date_range("2026-09-27", "2026-09-29") == [
        "2026-09-27",
        "2026-09-28",
        "2026-09-29",
    ]
