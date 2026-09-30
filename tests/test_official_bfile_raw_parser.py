# -*- coding: utf-8 -*-
from datetime import date

from research.official_bfile_raw_parser import (
    group_complete_races,
    parse_b_bytes,
    parse_b_entry,
)


def _entry(
    lane: int,
    *,
    racer="4321",
    name=b"ABCDEFGH",
    branch="1",
    age="35",
    weight="527",
    f="01",
    l="00",
    avgst="0016",
    nwin="0654",
    n2="4825",
    lwin="0611",
    l2="4510",
    motor="060",
    m2="4234",
    boat="021",
    b2="3712",
):
    raw = bytearray(b" " * 59)
    raw[0:2] = f"B{lane}".encode()
    raw[2:7] = racer.encode()
    raw[7:15] = name[:8].ljust(8, b" ")
    raw[15:16] = branch.encode()
    raw[16:18] = age.encode()
    raw[18:21] = weight.encode()
    raw[21:23] = f.encode()
    raw[23:25] = l.encode()
    raw[25:29] = avgst.encode()
    raw[29:33] = nwin.encode()
    raw[33:37] = n2.encode()
    raw[37:41] = lwin.encode()
    raw[41:45] = l2.encode()
    raw[45:48] = motor.encode()
    raw[48:52] = m2.encode()
    raw[52:55] = boat.encode()
    raw[55:59] = b2.encode()
    return bytes(raw)


def test_parse_candidate_layout():
    row = parse_b_entry(
        _entry(3),
        race_date="2025-07-01",
        venue_code="24",
        race_no=7,
    )
    assert row is not None
    assert row.race_id == "20250701_24_07"
    assert row.lane == 3
    assert row.racer_number == 4321
    assert row.age == 35
    assert row.weight == 52.7
    assert row.f_count == 1
    assert row.l_count == 0
    assert row.avg_st == 0.16
    assert row.national_win_rate == 6.54
    assert row.national_place2_rate == 48.25
    assert row.local_win_rate == 6.11
    assert row.local_place2_rate == 45.10
    assert row.motor_no == 60
    assert row.motor_place2_rate == 42.34
    assert row.boat_no == 21
    assert row.boat_place2_rate == 37.12


def test_multi_venue_daily_file_parser():
    lines = []
    for venue in ("05", "24"):
        lines.append(f"BB{venue}".encode())
        for rno in (1, 2):
            lines.append(f"BH{venue}{rno:02d}".encode())
            for lane in range(1, 7):
                lines.append(_entry(lane, racer=f"{4000+rno*10+lane:05d}"))
    rows = parse_b_bytes(b"\r\n".join(lines), date(2025, 7, 1))
    complete = group_complete_races(rows)
    assert len(rows) == 24
    assert set(complete) == {
        "20250701_05_01",
        "20250701_05_02",
        "20250701_24_01",
        "20250701_24_02",
    }


def test_short_or_implausible_entry_fails_closed():
    assert parse_b_entry(
        b"B1short",
        race_date="2025-07-01",
        venue_code="24",
        race_no=1,
    ) is None
    assert parse_b_entry(
        _entry(1, racer="00000"),
        race_date="2025-07-01",
        venue_code="24",
        race_no=1,
    ) is None
