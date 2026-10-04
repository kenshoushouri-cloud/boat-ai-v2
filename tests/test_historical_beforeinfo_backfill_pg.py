# -*- coding: utf-8 -*-
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import research.historical_beforeinfo_backfill_pg as m


def test_range_is_inclusive():
    assert m._date_range("2025-07-01", "2025-07-03") == [
        "2025-07-01",
        "2025-07-02",
        "2025-07-03",
    ]


def test_synthetic_snapshot_boundary_is_before_deadline():
    jst = ZoneInfo("Asia/Tokyo")
    deadline = datetime(2025, 7, 1, 8, 48, tzinfo=jst)
    snap = m._synthetic_snapshot_at(deadline, "2025-07-01")
    assert snap < deadline
    assert (deadline - snap).total_seconds() == 1


def test_source_contract_is_explicitly_historical_predeadline_assumed():
    assert m.SOURCE_CONTRACT == (
        "BOATRACE_OFFICIAL_ARCHIVED_BEFOREINFO_PREDEADLINE_ASSUMED_V1"
    )


def test_historical_label_is_fixed():
    assert m.SNAPSHOT_LABEL == "historical"


def test_modes_are_frozen():
    assert m.MODE_GENERIC == "generic"
    assert m.MODE_EXHIBITION_TIME_ONLY == "exhibition-time-only"
    assert m.MODES == (m.MODE_GENERIC, m.MODE_EXHIBITION_TIME_ONLY)


def test_exhibition_only_target_sql_has_no_weather_dependency():
    class Cur:
        def __init__(self):
            self.sql = ""
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def execute(self, sql, params):
            self.sql = sql
        def fetchall(self):
            return []

    class Conn:
        def __init__(self):
            self.cur = Cur()
        def cursor(self):
            return self.cur

    conn = Conn()
    assert m._target_races(
        conn, "2026-07-01", mode=m.MODE_EXHIBITION_TIME_ONLY
    ) == []
    sql = conn.cur.sql.lower()
    assert "exhibition_time" in sql
    assert "v2_realtime_weather_snapshots" not in sql
    assert "start_timing" not in sql


def test_plan_only_returns_before_http(monkeypatch):
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
        object(),
        DummySession(),
        "2026-07-01",
        write_enabled=False,
        sleep_sec=0.0,
        mode=m.MODE_EXHIBITION_TIME_ONLY,
        plan_only=True,
    )
    assert report["summary"]["target_missing_races"] == 1
    assert report["summary"]["plan_only_no_http"] == 1
    assert "http_requests" not in report["summary"]


def test_exhibition_only_write_function_cannot_fill_st_tilt_course_or_weather():
    source = Path("research/historical_beforeinfo_backfill_pg.py").read_text(
        encoding="utf-8"
    )
    start = source.index("def _upsert_exhibition_time_only(")
    end = source.index("\ndef process_day(", start)
    block = source[start:end].lower()
    assert "exhibition_time" in block
    assert "start_timing" not in block
    assert "tilt" not in block
    assert "exhibition_course" not in block
    assert "v2_realtime_weather_snapshots" not in block
