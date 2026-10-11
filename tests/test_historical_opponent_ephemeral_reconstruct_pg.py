# -*- coding: utf-8 -*-
from datetime import date
from pathlib import Path

import pytest

from research.historical_opponent_ephemeral_reconstruct_pg import (
    MAX_DAYS,
    date_range,
)


def test_exact_gap_range_is_supported():
    xs = date_range("2026-09-01", "2026-09-10")
    assert len(xs) == 10
    assert xs[0] == date(2026, 9, 1)
    assert xs[-1] == date(2026, 9, 10)
    assert MAX_DAYS == 10


def test_range_fails_closed_beyond_ten_days():
    with pytest.raises(ValueError):
        date_range("2026-09-01", "2026-09-11")


def test_ephemeral_reconstruct_source_has_no_db_write_path():
    source = Path(
        "research/historical_opponent_ephemeral_reconstruct_pg.py"
    ).read_text(encoding="utf-8").lower()

    assert "set transaction read only" in source
    assert "target_outcome_read" in source
    assert "database_write" in source
    for token in (
        "insert into",
        "update v2_",
        "delete from",
        "create table",
        "alter table",
        "drop table",
        "commit()",
    ):
        assert token not in source
