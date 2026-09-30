# -*- coding: utf-8 -*-
from datetime import date

from research.official_bfile_raw_parser import (
    group_complete_races,
    parse_b_bytes,
    parse_entry_line,
)


REAL = "1 4007榮田将彦46山口50B1 4.53 26.32 4.20 20.00 32  0.00 11 28.57 521         11"


def _entry_line(lane: int, racer: int) -> bytes:
    line = REAL.replace("1 4007", f"{lane} {racer:04d}", 1)
    raw = line.encode("cp932")
    assert len(raw) == 79
    return raw


def test_real_layout_example():
    raw = REAL.encode("cp932")
    row = parse_entry_line(
        raw,
        race_date="2025-07-01",
        venue_code="24",
        race_no=1,
    )
    assert row is not None
    assert row.race_id == "20250701_24_01"
    assert row.racer_number == 4007
    assert row.racer_name == "榮田将彦"
    assert row.age == 46
    assert row.branch == "山口"
    assert row.weight == 50.0
    assert row.racer_class_text == "B1"
    assert row.racer_class == 2
    assert row.national_win_rate == 4.53
    assert row.national_place2_rate == 26.32
    assert row.local_win_rate == 4.20
    assert row.local_place2_rate == 20.00
    assert row.motor_no == 32
    assert row.motor_place2_rate == 0.00
    assert row.boat_no == 11
    assert row.boat_place2_rate == 28.57


def test_multi_venue_human_readable_file():
    lines = [b"STARTB"]
    for venue in ("05", "24"):
        lines.append(f"{venue}BBGN".encode())
        for rno in (1, 2):
            lines.append(f"　{rno}Ｒ  一般".encode("cp932"))
            for lane in range(1, 7):
                lines.append(_entry_line(lane, 4000 + rno * 10 + lane))
    rows = parse_b_bytes(b"\r\n".join(lines), date(2025, 7, 1))
    complete = group_complete_races(rows)
    assert len(rows) == 24
    assert set(complete) == {
        "20250701_05_01",
        "20250701_05_02",
        "20250701_24_01",
        "20250701_24_02",
    }


def test_f_l_avg_st_are_not_fabricated_from_b_file():
    row = parse_entry_line(
        REAL.encode("cp932"),
        race_date="2025-07-01",
        venue_code="24",
        race_no=1,
    )
    assert row is not None
    assert not hasattr(row, "f_count")
    assert not hasattr(row, "l_count")
    assert not hasattr(row, "avg_st")
