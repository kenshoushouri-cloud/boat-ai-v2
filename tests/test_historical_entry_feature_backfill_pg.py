# -*- coding: utf-8 -*-
from research.historical_entry_feature_backfill_pg import (
    build_missing_patch,
    _date_range,
)


def test_fill_null_only_and_preserve_existing_value():
    existing = {
        "f_count": None,
        "avg_st": 0.14,
        "national_win_rate": None,
        "local_place2_rate": 0.0,
    }
    parsed = {
        "f_count": 1,
        "avg_st": 0.16,
        "national_win_rate": 6.42,
        "local_place2_rate": 33.3,
    }
    patch = build_missing_patch(existing, parsed)
    assert patch["f_count"] == 1
    assert patch["national_win_rate"] == 6.42
    assert "avg_st" not in patch
    assert "local_place2_rate" not in patch


def test_zero_is_valid_not_missing():
    patch = build_missing_patch(
        {"f_count": 0, "l_count": 0},
        {"f_count": 1, "l_count": 1},
    )
    assert patch == {}


def test_missing_source_value_is_not_written():
    patch = build_missing_patch(
        {"motor_place2_rate": None},
        {"motor_place2_rate": None},
    )
    assert patch == {}


def test_range_is_inclusive():
    assert _date_range("2025-07-01", "2025-07-03") == [
        "2025-07-01",
        "2025-07-02",
        "2025-07-03",
    ]
