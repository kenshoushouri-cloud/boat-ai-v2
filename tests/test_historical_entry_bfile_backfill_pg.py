# -*- coding: utf-8 -*-
import pytest

from research.historical_entry_bfile_backfill_pg import (
    _date_range,
    build_missing_patch,
)


def test_fill_missing_only():
    patch = build_missing_patch(
        {
            "racer_name": None,
            "branch": "大阪",
            "national_win_rate": None,
            "motor_no": "",
        },
        {
            "racer_name": "山田太郎",
            "branch": "兵庫",
            "national_win_rate": 6.12,
            "motor_no": 42,
        },
    )
    assert patch == {
        "racer_name": "山田太郎",
        "national_win_rate": 6.12,
        "motor_no": 42,
    }


def test_range_guard():
    assert _date_range("2025-07-01", "2025-07-03") == [
        "2025-07-01",
        "2025-07-02",
        "2025-07-03",
    ]
    with pytest.raises(ValueError):
        _date_range("2025-07-03", "2025-07-01")
