# -*- coding: utf-8 -*-
"""Raw parser for BOAT RACE official daily B program files.

Validated raw 2025-07-01 structure:
- venue section marker: NNBBGN (for example 24BBGN);
- race header: Japanese human-readable line beginning １Ｒ .. １２Ｒ;
- six 79-byte entry lines beginning 1 .. 6.

The official B program table does not contain F/L or average ST.
Those remain sourced from official archived racelist pages.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import re
import unicodedata
from typing import Any, Iterable


CLASS_MAP = {"B2": 1, "B1": 2, "A2": 3, "A1": 4}


@dataclass(frozen=True)
class BEntry:
    race_date: str
    venue_code: str
    race_no: int
    lane: int
    racer_number: int
    racer_name: str | None
    age: int | None
    branch: str | None
    weight: float | None
    racer_class_text: str | None
    racer_class: int | None
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
        return raw[start:end].decode("cp932", errors="replace").replace("�", "").strip()
    except Exception:
        return ""


def _int_text(value: str) -> int | None:
    text = value.strip()
    if not text or not text.lstrip("+-").isdigit():
        return None
    try:
        return int(text)
    except Exception:
        return None


def _float_text(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        return round(float(text), 4)
    except Exception:
        return None


def _bounded_int(raw: bytes, start: int, end: int, low: int, high: int) -> int | None:
    value = _int_text(_ascii(raw, start, end))
    return value if value is not None and low <= value <= high else None


def _bounded_float(raw: bytes, start: int, end: int, low: float, high: float) -> float | None:
    value = _float_text(_ascii(raw, start, end))
    return value if value is not None and low <= value <= high else None


def parse_entry_line(
    raw: bytes,
    *,
    race_date: str,
    venue_code: str,
    race_no: int,
) -> BEntry | None:
    """Parse one validated 79-byte human-readable entry line."""
    raw = raw.rstrip(b"\r")
    if len(raw) != 79 or raw[:1] not in b"123456" or raw[1:2] != b" ":
        return None

    lane = int(chr(raw[0]))
    racer_number = _bounded_int(raw, 2, 6, 1000, 9999)
    if racer_number is None:
        return None

    racer_class_text = _ascii(raw, 22, 24) or None
    if racer_class_text not in CLASS_MAP:
        racer_class_text = None

    return BEntry(
        race_date=race_date,
        venue_code=venue_code.zfill(2),
        race_no=int(race_no),
        lane=lane,
        racer_number=racer_number,
        racer_name=_cp932(raw, 6, 14) or None,
        age=_bounded_int(raw, 14, 16, 15, 99),
        branch=_cp932(raw, 16, 20) or None,
        weight=_bounded_float(raw, 20, 22, 30.0, 100.0),
        racer_class_text=racer_class_text,
        racer_class=CLASS_MAP.get(racer_class_text or ""),
        national_win_rate=_bounded_float(raw, 25, 29, 0.0, 10.0),
        national_place2_rate=_bounded_float(raw, 30, 35, 0.0, 100.0),
        local_win_rate=_bounded_float(raw, 36, 40, 0.0, 10.0),
        local_place2_rate=_bounded_float(raw, 41, 46, 0.0, 100.0),
        motor_no=_bounded_int(raw, 47, 49, 1, 99),
        motor_place2_rate=_bounded_float(raw, 50, 55, 0.0, 100.0),
        boat_no=_bounded_int(raw, 56, 58, 1, 99),
        boat_place2_rate=_bounded_float(raw, 59, 64, 0.0, 100.0),
    )


def _race_number_from_header(raw: bytes) -> int | None:
    try:
        text = raw.decode("cp932", errors="replace")
    except Exception:
        return None
    text = unicodedata.normalize("NFKC", text).strip()
    match = re.match(r"^(\d{1,2})R\b", text, flags=re.I)
    if not match:
        return None
    value = int(match.group(1))
    return value if 1 <= value <= 12 else None


def parse_b_bytes(raw_bytes: bytes, target_date: date) -> list[BEntry]:
    """Parse all venue/race/entry rows from one official daily B TXT."""
    entries: list[BEntry] = []
    venue_code: str | None = None
    race_no: int | None = None

    for raw in raw_bytes.splitlines():
        raw = raw.rstrip(b"\r")
        if not raw:
            continue

        if len(raw) == 6:
            try:
                marker = raw.decode("ascii")
            except Exception:
                marker = ""
            match = re.fullmatch(r"(\d{2})BBGN", marker)
            if match and 1 <= int(match.group(1)) <= 24:
                venue_code = match.group(1)
                race_no = None
                continue

        header_race = _race_number_from_header(raw)
        if header_race is not None:
            race_no = header_race
            continue

        if venue_code is None or race_no is None:
            continue
        item = parse_entry_line(
            raw,
            race_date=target_date.isoformat(),
            venue_code=venue_code,
            race_no=race_no,
        )
        if item is not None:
            entries.append(item)

    return entries


def group_complete_races(entries: Iterable[BEntry]) -> dict[str, list[BEntry]]:
    grouped: dict[str, list[BEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.race_id, []).append(entry)
    return {
        race_id: sorted(rows, key=lambda x: x.lane)
        for race_id, rows in grouped.items()
        if len(rows) == 6 and {row.lane for row in rows} == {1, 2, 3, 4, 5, 6}
    }
