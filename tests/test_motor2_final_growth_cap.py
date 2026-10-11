from datetime import datetime, timezone

import pytest

from research.motor2_final_growth_cap import (
    DEFAULT_MODE,
    build_snapshot_key,
    logical_unique_key,
    projected_distinct_rows,
)


def _t(h, m):
    return datetime(2026, 9, 12, h, m, tzinfo=timezone.utc)


def test_default_mode_preserves_current_timestamped_behavior():
    assert DEFAULT_MODE == "timestamped"
    first = build_snapshot_key("2026-09-12", _t(8, 0))
    second = build_snapshot_key("2026-09-12", _t(8, 15))
    assert first != second
    assert first.startswith("20260912_final_")


def test_latest_per_race_reuses_key_across_repeated_final_runs():
    first = logical_unique_key("202609120101", "1-2-3", "2026-09-12", _t(8, 0), "latest_per_race")
    second = logical_unique_key("202609120101", "1-2-3", "2026-09-12", _t(8, 15), "latest_per_race")
    assert first == second
    assert first[-1] == "20260912_final_latest"


def test_latest_per_race_keeps_races_and_tickets_independent():
    base = logical_unique_key("202609120101", "1-2-3", "2026-09-12", _t(8, 0), "latest_per_race")
    other_race = logical_unique_key("202609120102", "1-2-3", "2026-09-12", _t(8, 15), "latest_per_race")
    other_ticket = logical_unique_key("202609120101", "1-3-2", "2026-09-12", _t(8, 15), "latest_per_race")
    assert len({base, other_race, other_ticket}) == 3


def test_compact_mode_caps_repeated_run_row_growth():
    races = ["r1", "r2", "r3"]
    tickets = ["1-2-3", "1-3-2", "2-1-3", "2-3-1"]
    times = [_t(8, 0), _t(8, 15), _t(8, 30), _t(8, 45)]
    timestamped = projected_distinct_rows(races, tickets, times, "2026-09-12", "timestamped")
    compact = projected_distinct_rows(races, tickets, times, "2026-09-12", "latest_per_race")
    assert timestamped == 48
    assert compact == 12
    assert compact * len(times) == timestamped


def test_unknown_mode_fails_closed():
    with pytest.raises(ValueError):
        build_snapshot_key("2026-09-12", _t(8, 0), "mystery")
