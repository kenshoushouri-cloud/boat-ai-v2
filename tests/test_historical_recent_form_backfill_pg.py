# -*- coding: utf-8 -*-
from collections import deque

from research.historical_recent_form_backfill_pg import (
    append_result_rows,
    build_target_patches,
    recent_form_for,
)


def _row(day, race_id, racer, st, finish, race_no=1):
    return {
        "race_date": day,
        "race_id": race_id,
        "venue_id": "01",
        "race_no": race_no,
        "lane": 1,
        "racer_number": racer,
        "start_course": 1,
        "start_timing": st,
        "finish_position": finish,
        "finish_status": "0" + str(finish),
        "motor_no": "10",
        "boat_no": "20",
    }


def test_recent_form_is_newest_first():
    histories = {}
    append_result_rows(
        histories,
        [
            _row("2025-06-01", "A", 1001, 0.12, 2),
            _row("2025-06-03", "B", 1001, 0.15, 1),
        ],
    )
    out = recent_form_for(histories, 1001)
    assert [x["race_id"] for x in out] == ["B", "A"]
    assert out[0]["start_timing"] == 0.15


def test_history_is_capped_at_five():
    histories = {}
    append_result_rows(
        histories,
        [
            _row(f"2025-06-{i:02d}", f"R{i}", 1001, 0.10 + i / 100, (i % 6) + 1)
            for i in range(1, 8)
        ],
    )
    out = recent_form_for(histories, 1001)
    assert len(out) == 5
    assert out[0]["race_id"] == "R7"
    assert out[-1]["race_id"] == "R3"


def test_target_patch_uses_only_history_already_present():
    histories = {}
    append_result_rows(
        histories,
        [_row("2025-06-30", "P", 1001, 0.11, 3)],
    )
    target = [{"race_id": "T", "lane": 4, "racer_number": 1001}]
    patches = build_target_patches(target, histories)
    assert len(patches) == 1
    assert patches[0]["recent_form"][0]["race_id"] == "P"


def test_no_history_means_no_patch():
    patches = build_target_patches(
        [{"race_id": "T", "lane": 4, "racer_number": 9999}],
        {},
    )
    assert patches == []


def test_append_same_day_result_changes_only_future_snapshot():
    histories = {1001: deque(maxlen=5)}
    append_result_rows(histories, [_row("2025-06-30", "P", 1001, 0.11, 3)])
    before = recent_form_for(histories, 1001)
    assert [x["race_id"] for x in before] == ["P"]

    # This simulates the script's chronology: target-day patches are built first,
    # then target-day K results are appended for use by the NEXT calendar day.
    append_result_rows(histories, [_row("2025-07-01", "T", 1001, 0.09, 1)])
    after = recent_form_for(histories, 1001)
    assert [x["race_id"] for x in after] == ["T", "P"]
