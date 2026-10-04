# -*- coding: utf-8 -*-
from datetime import datetime
from zoneinfo import ZoneInfo

from research.historical_beforeinfo_backfill_pg import (
    SOURCE_CONTRACT,
    _date_range,
    _synthetic_snapshot_at,
    MODE_EXHIBITION_TIME_ONLY,
    MODE_GENERIC,
    MODES,
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


def test_modes_are_frozen():
    assert MODE_GENERIC in MODES
    assert MODE_EXHIBITION_TIME_ONLY in MODES
    assert MODE_EXHIBITION_TIME_ONLY == "exhibition-time-only"


def test_exhibition_only_source_does_not_require_weather_targeting():
    from pathlib import Path
    s = Path("research/historical_beforeinfo_backfill_pg.py").read_text(
        encoding="utf-8"
    )
    marker = "if mode == MODE_EXHIBITION_TIME_ONLY:"
    start = s.index(marker)
    end = s.index("    with conn.cursor() as cur:", start + len(marker))
    block = s[start:end]
    assert "v2_realtime_weather_snapshots" not in block


def test_plan_only_returns_before_http(monkeypatch):
    import research.historical_beforeinfo_backfill_pg as m

    class DummyConn:
        pass

    monkeypatch.setattr(
        m,
        "_target_races",
        lambda conn, target_date, mode=m.MODE_GENERIC: [
            {"race_id": "x", "venue_id": "01", "race_no": 1}
        ],
    )

    class DummySession:
        def get(self, *args, **kwargs):
            raise AssertionError("HTTP must not run in plan_only")

    report = m.process_day(
        DummyConn(),
        DummySession(),
        "2026-07-01",
        write_enabled=False,
        sleep_sec=0.0,
        mode=m.MODE_EXHIBITION_TIME_ONLY,
        plan_only=True,
    )
    assert report["summary"]["target_missing_races"] == 1
    assert report["summary"]["plan_only_no_http"] == 1
