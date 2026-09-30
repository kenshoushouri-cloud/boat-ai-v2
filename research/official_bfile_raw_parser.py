# -*- coding: utf-8 -*-
"""Raw BOAT RACE official daily B-file parser for historical pre-race inputs.

The daily B archive is a pre-race program source. This parser intentionally
extracts only entry/program fields and does not parse result or payout data.

B record layout is validated against the project's existing official archived
racelist data before any importer is allowed to write PostgreSQL.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Any, Iterable


@dataclass(frozen=True)
class BEntry:
    race_date: str
    venue_code: str
    race_no: int
    lane: int
    racer_number: int | None
    racer_name: str | None
    branch_code: str | None
    age: int | None
    weight: float | None
    f_count: int | None
    l_count: int | None
    avg_st: float | None
    national_win_rate: float | None
    national_place2_rate: float | None
    local_win_rate: float | None
    local_place2_rate: float | None
    motor_no: int | None
    motor_place2_rate: float | None
    boat_no: int | None
    boat_place2_rate: float | None

    @property
    def race_id(self) -> str:
        return (
            f"{self.race_date.replace('-', '')}_"
            f"{self.venue_code.zfill(2)}_{self.race_no:02d}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "race_id": self.race_id}


def _ascii(raw: bytes, start: int, end: int) -> str:
    try:
        return raw[start:end].decode("ascii").strip()
    except Exception:
        return ""


def _cp932(raw: bytes, start: int, end: int) -> str:
    try:
        value = raw[start:end].decode("cp932", errors="replace").strip()
    except Exception:
        return ""
    return value.replace("�", "").strip()


def _int(raw: bytes, start: int, end: int) -> int | None:
    text = _ascii(raw, start, end)
    if not text or not text.lstrip("+-").isdigit():
        return None
    try:
        return int(text)
    except Exception:
        return None


def _scaled(
    raw: bytes,
    start: int,
    end: int,
    scale: float,
) -> float | None:
    value = _int(raw, start, end)
    if value is None:
        return None
    return round(value * scale, 4)


def _bounded_int(
    raw: bytes,
    start: int,
    end: int,
    low: int,
    high: int,
) -> int | None:
    value = _int(raw, start, end)
    if value is None or not low <= value <= high:
        return None
    return value


def _bounded_scaled(
    raw: bytes,
    start: int,
    end: int,
    scale: float,
    low: float,
    high: float,
) -> float | None:
    value = _scaled(raw, start, end, scale)
    if value is None or not low <= value <= high:
        return None
    return value


def parse_b_entry(
    raw: bytes,
    *,
    race_date: str,
    venue_code: str,
    race_no: int,
) -> BEntry | None:
    """Parse one B1..B6 record using the validated-candidate byte layout.

    The offsets intentionally remain isolated here so live parity can validate
    every useful metric before any historical importer is promoted.
    """
    if len(raw) < 59:
        return None
    try:
        rtype = raw[:2].decode("ascii")
    except Exception:
        return None
    if len(rtype) != 2 or rtype[0] != "B" or rtype[1] not in "123456":
        return None

    lane = int(rtype[1])
    racer_number = _bounded_int(raw, 2, 7, 1000, 99999)
    if racer_number is None:
        return None

    name = _cp932(raw, 7, 15) or None
    branch = _ascii(raw, 15, 16) or None

    return BEntry(
        race_date=race_date,
        venue_code=venue_code.zfill(2),
        race_no=int(race_no),
        lane=lane,
        racer_number=racer_number,
        racer_name=name,
        branch_code=branch,
        age=_bounded_int(raw, 16, 18, 15, 99),
        weight=_bounded_scaled(raw, 18, 21, 0.1, 30.0, 100.0),
        f_count=_bounded_int(raw, 21, 23, 0, 20),
        l_count=_bounded_int(raw, 23, 25, 0, 20),
        avg_st=_bounded_scaled(raw, 25, 29, 0.01, 0.0, 1.5),
        national_win_rate=_bounded_scaled(raw, 29, 33, 0.01, 0.0, 10.0),
        national_place2_rate=_bounded_scaled(raw, 33, 37, 0.01, 0.0, 100.0),
        local_win_rate=_bounded_scaled(raw, 37, 41, 0.01, 0.0, 10.0),
        local_place2_rate=_bounded_scaled(raw, 41, 45, 0.01, 0.0, 100.0),
        motor_no=_bounded_int(raw, 45, 48, 1, 999),
        motor_place2_rate=_bounded_scaled(raw, 48, 52, 0.01, 0.0, 100.0),
        boat_no=_bounded_int(raw, 52, 55, 1, 999),
        boat_place2_rate=_bounded_scaled(raw, 55, 59, 0.01, 0.0, 100.0),
    )


def parse_b_bytes(raw_bytes: bytes, target_date: date) -> list[BEntry]:
    """Parse all BB/BH/B1..B6 records from a multi-venue daily B file."""
    entries: list[BEntry] = []
    venue_code = ""
    race_no: int | None = None

    for raw in raw_bytes.splitlines():
        raw = raw.rstrip(b"\r")
        if len(raw) < 2:
            continue
        try:
            rtype = raw[:2].decode("ascii")
        except Exception:
            continue

        if rtype == "BB":
            venue = _ascii(raw, 2, 4)
            if venue.isdigit() and 1 <= int(venue) <= 24:
                venue_code = venue.zfill(2)
            race_no = None
            continue

        if rtype == "BH":
            venue = _ascii(raw, 2, 4)
            if venue.isdigit() and 1 <= int(venue) <= 24:
                venue_code = venue.zfill(2)
            rno = _int(raw, 4, 6)
            race_no = rno if rno is not None and 1 <= rno <= 12 else None
            continue

        if (
            len(rtype) == 2
            and rtype[0] == "B"
            and rtype[1] in "123456"
            and venue_code
            and race_no is not None
        ):
            item = parse_b_entry(
                raw,
                race_date=target_date.isoformat(),
                venue_code=venue_code,
                race_no=race_no,
            )
            if item is not None:
                entries.append(item)

    return entries


def group_complete_races(entries: Iterable[BEntry]) -> dict[str, list[BEntry]]:
    out: dict[str, list[BEntry]] = {}
    for entry in entries:
        out.setdefault(entry.race_id, []).append(entry)
    return {
        race_id: sorted(rows, key=lambda x: x.lane)
        for race_id, rows in out.items()
        if len(rows) == 6 and {x.lane for x in rows} == {1, 2, 3, 4, 5, 6}
    }
