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
    assert "start_timing=" not in block
    assert "start_timing," not in block
    assert "tilt=" not in block
    assert "tilt," not in block
    assert "exhibition_course=" not in block
    assert "exhibition_course," not in block
    assert "v2_realtime_weather_snapshots" not in block


def _valid_six_rows():
    times = [6.70, 6.71, 6.72, 6.73, 6.74, 6.75]
    return [
        {
            "lane": lane,
            "exhibition_time": times[lane - 1],
            "exhibition_time_rank": lane,
            "exhibition_time_diff": round(times[lane - 1] - times[0], 3),
        }
        for lane in range(1, 7)
    ]


def test_exhibition_time_only_uses_historical_parser_v3(monkeypatch):
    sentinel = _valid_six_rows()
    monkeypatch.setattr(
        m.historical_parser_v3,
        "parse_exhibition",
        lambda html: sentinel,
    )
    monkeypatch.setattr(
        m.rt,
        "parse_exhibition",
        lambda html: (_ for _ in ()).throw(
            AssertionError("realtime parser must not be used")
        ),
    )
    assert m._parse_exhibition_for_mode(
        "<html/>",
        mode=m.MODE_EXHIBITION_TIME_ONLY,
    ) == sentinel


def test_generic_mode_keeps_realtime_parser(monkeypatch):
    sentinel = _valid_six_rows()
    monkeypatch.setattr(m.rt, "parse_exhibition", lambda html: sentinel)
    monkeypatch.setattr(
        m.historical_parser_v3,
        "parse_exhibition",
        lambda html: (_ for _ in ()).throw(
            AssertionError("historical parser must not be used")
        ),
    )
    assert m._parse_exhibition_for_mode(
        "<html/>",
        mode=m.MODE_GENERIC,
    ) == sentinel


def test_exhibition_time_validator_requires_exact_six_and_valid_time_rank_diff():
    rows = _valid_six_rows()
    assert len(m._validated_exhibition_time_rows(rows)) == 6

    bad = [dict(x) for x in rows]
    bad[0]["exhibition_time"] = 99.0
    assert m._validated_exhibition_time_rows(bad) == []

    bad = [dict(x) for x in rows]
    bad[5]["lane"] = 5
    assert m._validated_exhibition_time_rows(bad) == []

    bad = [dict(x) for x in rows]
    bad[3]["exhibition_time_rank"] = None
    assert m._validated_exhibition_time_rows(bad) == []


def test_invalid_historical_parse_never_writes(monkeypatch):
    monkeypatch.setattr(
        m,
        "_target_races",
        lambda conn, target_date, mode=m.MODE_GENERIC: [
            {
                "race_id": "x",
                "race_date": "2026-07-01",
                "venue_id": "01",
                "race_no": 1,
                "deadline_at": None,
            }
        ],
    )
    monkeypatch.setattr(m, "_fetch", lambda session, url, sleep_sec: "<html/>")
    monkeypatch.setattr(m.rt, "_looks_no_data", lambda html: False)
    monkeypatch.setattr(
        m.historical_parser_v3,
        "inspect_exhibition_time_page",
        lambda html: {
            "status": m.historical_parser_v3.EXHIBITION_STATUS_PARSER_FAILURE,
            "valid_time_count": 0,
            "lanes": [],
            "rows": [],
            "source": "test",
        },
    )
    monkeypatch.setattr(
        m,
        "_upsert_exhibition_time_only",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("invalid parse must never write")
        ),
    )

    class Conn:
        def commit(self):
            raise AssertionError("invalid parse must not commit")
        def rollback(self):
            pass

    report = m.process_day(
        Conn(),
        object(),
        "2026-07-01",
        write_enabled=True,
        sleep_sec=0.0,
        mode=m.MODE_EXHIBITION_TIME_ONLY,
        plan_only=False,
    )
    assert report["summary"]["target_missing_races"] == 1
    assert report["summary"]["exhibition_parse_rejected_races"] == 1
    assert report["summary"].get("exhibition_rows_touched", 0) == 0


def test_batch_parse_quality_fails_per_day_when_target_has_zero_usable_rows():
    status = m._batch_parse_quality_status(
        mode=m.MODE_EXHIBITION_TIME_ONLY,
        reports=[
            {
                "target_date": "2026-07-01",
                "summary": {
                    "target_missing_races": 4,
                    "exhibition_rows_usable": 0,
                    "exhibition_complete_races": 0,
                },
            },
            {
                "target_date": "2026-07-02",
                "summary": {
                    "target_missing_races": 1,
                    "exhibition_rows_usable": 6,
                    "exhibition_complete_races": 1,
                },
            },
        ],
        plan_only=False,
    )
    assert status == "FAIL_DAY_ZERO_USABLE"

    status = m._batch_parse_quality_status(
        mode=m.MODE_EXHIBITION_TIME_ONLY,
        reports=[
            {
                "target_date": "2026-07-01",
                "summary": {
                    "target_missing_races": 4,
                    "exhibition_rows_usable": 24,
                    "exhibition_complete_races": 4,
                },
            },
            {
                "target_date": "2026-07-02",
                "summary": {"target_missing_races": 0},
            },
        ],
        plan_only=False,
    )
    assert status == "PASS"

    status = m._batch_parse_quality_status(
        mode=m.MODE_EXHIBITION_TIME_ONLY,
        reports=[{"target_date": "2026-07-01", "summary": {"target_missing_races": 53}}],
        plan_only=True,
    )
    assert status == "NOT_APPLICABLE_PLAN_ONLY"




def test_official_partial_is_visible_but_never_written(monkeypatch):
    monkeypatch.setattr(
        m,
        "_target_races",
        lambda conn, target_date, mode=m.MODE_GENERIC: [
            {
                "race_id": "x",
                "race_date": "2026-07-01",
                "venue_id": "01",
                "race_no": 1,
                "deadline_at": None,
            }
        ],
    )
    monkeypatch.setattr(m, "_fetch", lambda session, url, sleep_sec: "<html/>")
    monkeypatch.setattr(m.rt, "_looks_no_data", lambda html: False)
    partial_rows = [
        {"lane": lane, "exhibition_time": 6.70 + lane / 100}
        for lane in range(2, 7)
    ]
    monkeypatch.setattr(
        m.historical_parser_v3,
        "inspect_exhibition_time_page",
        lambda html: {
            "status": m.historical_parser_v3.EXHIBITION_STATUS_OFFICIAL_PARTIAL,
            "valid_time_count": 5,
            "lanes": [2, 3, 4, 5, 6],
            "rows": partial_rows,
            "source": "primary_structured_rows",
        },
    )
    monkeypatch.setattr(
        m,
        "_upsert_exhibition_time_only",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("official partial must never write")
        ),
    )

    class Conn:
        def commit(self):
            raise AssertionError("official partial must not commit")
        def rollback(self):
            pass

    report = m.process_day(
        Conn(),
        object(),
        "2026-07-01",
        write_enabled=True,
        sleep_sec=0.0,
        mode=m.MODE_EXHIBITION_TIME_ONLY,
        plan_only=False,
    )
    s = report["summary"]
    assert s["exhibition_official_partial_races"] == 1
    assert s["exhibition_official_partial_rows"] == 5
    assert s["exhibition_parse_rejected_races"] == 1
    assert s.get("exhibition_rows_touched", 0) == 0


def test_batch_status_distinguishes_official_partial_from_parser_failure():
    partial = m._batch_parse_quality_status(
        mode=m.MODE_EXHIBITION_TIME_ONLY,
        reports=[{
            "summary": {
                "target_missing_races": 1,
                "exhibition_rows_usable": 0,
                "exhibition_complete_races": 0,
                "exhibition_official_partial_races": 1,
            }
        }],
        plan_only=False,
    )
    assert partial == "FAIL_DAY_OFFICIAL_PARTIAL_ONLY"

    failure = m._batch_parse_quality_status(
        mode=m.MODE_EXHIBITION_TIME_ONLY,
        reports=[{
            "summary": {
                "target_missing_races": 1,
                "exhibition_rows_usable": 0,
                "exhibition_complete_races": 0,
                "exhibition_parser_failure_races": 1,
            }
        }],
        plan_only=False,
    )
    assert failure == "FAIL_DAY_PARSER_FAILURE"



def test_official_absent_is_visible_but_never_written(monkeypatch):
    monkeypatch.setattr(
        m,
        "_target_races",
        lambda conn, target_date, mode=m.MODE_GENERIC: [{
            "race_id": "x",
            "race_date": "2026-07-29",
            "venue_id": "09",
            "race_no": 1,
            "deadline_at": None,
        }],
    )
    monkeypatch.setattr(m, "_fetch", lambda session, url, sleep_sec: "<html/>")
    monkeypatch.setattr(m.rt, "_looks_no_data", lambda html: False)
    monkeypatch.setattr(
        m.historical_parser_v3,
        "inspect_exhibition_time_page",
        lambda html: {
            "status": m.historical_parser_v3.EXHIBITION_STATUS_OFFICIAL_ABSENT,
            "valid_time_count": 0,
            "lanes": [1, 2, 3, 4, 5, 6],
            "rows": [],
            "source": "primary_structured_rows_no_times",
        },
    )
    monkeypatch.setattr(
        m,
        "_upsert_exhibition_time_only",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("official absent must never write")
        ),
    )

    class Conn:
        def commit(self):
            raise AssertionError("official absent must not commit")
        def rollback(self):
            pass

    report = m.process_day(
        Conn(),
        object(),
        "2026-07-29",
        write_enabled=True,
        sleep_sec=0.0,
        mode=m.MODE_EXHIBITION_TIME_ONLY,
        plan_only=False,
    )
    s = report["summary"]
    assert s["exhibition_official_absent_races"] == 1
    assert s["exhibition_parse_rejected_races"] == 1
    assert s.get("exhibition_rows_touched", 0) == 0


def test_batch_status_distinguishes_official_absent():
    status = m._batch_parse_quality_status(
        mode=m.MODE_EXHIBITION_TIME_ONLY,
        reports=[{
            "summary": {
                "target_missing_races": 1,
                "exhibition_rows_usable": 0,
                "exhibition_complete_races": 0,
                "exhibition_official_absent_races": 1,
            }
        }],
        plan_only=False,
    )
    assert status == "FAIL_DAY_OFFICIAL_ABSENT_ONLY"



def test_terminal_unfillable_manifest_has_exact_verified_july_53():
    ids = m._terminal_unfillable_exhibition_ids()
    assert len(ids) == 53
    assert "20260701_10_08" in ids
    assert "20260729_09_12" in ids


def test_exhibition_only_target_excludes_terminal_unfillable(monkeypatch):
    class Cur:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def execute(self, sql, params):
            pass
        def fetchall(self):
            return [
                {"race_id": "20260701_10_08", "race_date": "2026-07-01", "venue_id": "10", "race_no": 8},
                {"race_id": "keep_me", "race_date": "2026-07-01", "venue_id": "10", "race_no": 9},
            ]

    class Conn:
        def cursor(self):
            return Cur()

    monkeypatch.setattr(
        m,
        "_terminal_unfillable_exhibition_ids",
        lambda: {"20260701_10_08"},
    )
    rows = m._target_races(
        Conn(),
        "2026-07-01",
        mode=m.MODE_EXHIBITION_TIME_ONLY,
    )
    assert [row["race_id"] for row in rows] == ["keep_me"]
