# -*- coding: utf-8 -*-
from datetime import datetime
from zoneinfo import ZoneInfo

from research.historical_beforeinfo_backfill_pg import (
    SOURCE_CONTRACT,
    _date_range,
    _synthetic_snapshot_at,
)


def test_range_is_inclusive():
    assert _date_range("2025-07-01", "2025-07-03") == [
        "2025-07-01",
        "2025-07-02",
        "2025-07-03",
    ]


def test_synthetic_snapshot_boundary_is_before_deadline():
    jst = ZoneInfo("Asia/Tokyo")
    deadline = datetime(2025, 7, 1, 8, 48, tzinfo=jst)
    snap = _synthetic_snapshot_at(deadline, "2025-07-01")
    assert snap < deadline
    assert (deadline - snap).total_seconds() == 1


def test_source_contract_is_explicitly_historical_predeadline_assumed():
    assert SOURCE_CONTRACT == (
        "BOATRACE_OFFICIAL_ARCHIVED_BEFOREINFO_PREDEADLINE_ASSUMED_V1"
    )


def test_historical_label_is_fixed():
    from research.historical_beforeinfo_backfill_pg import SNAPSHOT_LABEL
    assert SNAPSHOT_LABEL == "historical"
