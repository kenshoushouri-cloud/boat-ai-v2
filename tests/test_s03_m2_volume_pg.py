# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from research.s03_m2_volume_pg import (
    aggregate_s03_m2_volume,
    motor2_score,
)


def _entries(values):
    return [
        {"lane": i + 1, "motor_place2_rate": value}
        for i, value in enumerate(values)
    ]


def test_motor2_score_matches_positive_direction():
    score = motor2_score(_entries([60, 50, 40, 30, 20, 10]), "1-2-3")
    assert score is not None
    assert score > 0


def test_result_blind_volume_counts_unique_positive_races():
    t0 = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 29, 1, 0, tzinfo=timezone.utc)
    rows = [
        {"race_date": "2026-09-29", "race_id": "A", "ticket": "1-2-3", "snapshot_at": t0, "deadline_at": t1},
        {"race_date": "2026-09-29", "race_id": "B", "ticket": "1-2-3", "snapshot_at": t0, "deadline_at": t1},
    ]
    entries = {
        "A": _entries([60, 50, 40, 30, 20, 10]),
        "B": _entries([60, 50, 40, 30, 20, 10]),
    }
    out = aggregate_s03_m2_volume(rows, entries)
    day = out["daily"]["2026-09-29"]
    assert day["m2_positive_rows"] == 2
    assert day["m2_positive_unique_races"] == 2
    assert day["within_1_to_3_race_context"] is True


def test_late_snapshot_is_rejected_before_motor_score():
    t0 = datetime(2026, 9, 29, 1, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
    rows = [
        {"race_date": "2026-09-29", "race_id": "A", "ticket": "1-2-3", "snapshot_at": t0, "deadline_at": t1},
    ]
    out = aggregate_s03_m2_volume(rows, {"A": _entries([60, 50, 40, 30, 20, 10])})
    day = out["daily"]["2026-09-29"]
    assert day["timing_rejected"] == 1
    assert day.get("m2_positive_rows", 0) == 0
    assert day["below_1_race_context"] is True
