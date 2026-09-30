# -*- coding: utf-8 -*-
from datetime import date

import pytest

from research.historical_opponent_pressure_replay_pg import (
    HISTORICAL_MODEL_VERSION,
    date_range,
)
from research import _historical_opponent_adapter as adapter


def test_historical_model_version_cannot_match_production_v2():
    assert HISTORICAL_MODEL_VERSION == 102
    assert HISTORICAL_MODEL_VERSION != adapter.mod.VERSION_CODE


def test_date_range_is_bounded_and_starts_at_frozen_train_start():
    xs = date_range("2025-07-01", "2025-07-03")
    assert xs == [date(2025,7,1), date(2025,7,2), date(2025,7,3)]
    with pytest.raises(ValueError):
        date_range("2025-06-30", "2025-07-01")


def test_batch_is_limited_to_seven_days():
    assert len(date_range("2025-09-01", "2025-09-07")) == 7
    with pytest.raises(ValueError):
        date_range("2025-09-01", "2025-09-08")
