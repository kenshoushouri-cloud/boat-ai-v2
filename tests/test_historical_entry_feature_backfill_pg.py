# -*- coding: utf-8 -*-
from research.historical_entry_feature_backfill_pg import (
    MODEL_CRITICAL_RESIDUAL_FIELDS,
    RESIDUAL_FIELDS,
    TEXT_DB_FIELDS,
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


def test_text_db_fields_include_racer_metadata_and_numbers():
    assert TEXT_DB_FIELDS == {
        "racer_name",
        "branch",
        "origin",
        "motor_no",
        "boat_no",
    }


def test_missing_racer_metadata_is_fillable_but_existing_is_preserved():
    patch = build_missing_patch(
        {
            "racer_name": None,
            "branch": "",
            "origin": "大阪",
        },
        {
            "racer_name": "山田 太郎",
            "branch": "大阪",
            "origin": "兵庫",
        },
    )
    assert patch["racer_name"] == "山田 太郎"
    assert patch["branch"] == "大阪"
    assert "origin" not in patch


def test_residual_profile_contains_only_fields_not_supplied_by_b_table():
    assert RESIDUAL_FIELDS == (
        "origin",
        "f_count",
        "l_count",
        "avg_st",
        "national_place3_rate",
        "local_place3_rate",
        "motor_place3_rate",
        "boat_place3_rate",
    )


def test_residual_patch_ignores_bfile_fields():
    patch = build_missing_patch(
        {
            "racer_name": None,
            "national_win_rate": None,
            "f_count": None,
            "avg_st": None,
        },
        {
            "racer_name": "山田 太郎",
            "national_win_rate": 6.50,
            "f_count": 1,
            "avg_st": 0.15,
        },
        fields=RESIDUAL_FIELDS,
    )
    assert patch == {"f_count": 1, "avg_st": 0.15}


def test_model_critical_residual_excludes_identity_origin():
    assert MODEL_CRITICAL_RESIDUAL_FIELDS == (
        "f_count",
        "l_count",
        "avg_st",
        "national_place3_rate",
        "local_place3_rate",
        "motor_place3_rate",
        "boat_place3_rate",
    )
    assert "origin" not in MODEL_CRITICAL_RESIDUAL_FIELDS


def test_model_critical_patch_does_not_spend_http_work_on_identity_only_gap():
    patch = build_missing_patch(
        {
            "origin": None,
            "f_count": 0,
            "avg_st": 0.15,
        },
        {
            "origin": "大阪",
            "f_count": 1,
            "avg_st": 0.16,
        },
        fields=MODEL_CRITICAL_RESIDUAL_FIELDS,
    )
    assert patch == {}
