"""Convert *supplied* boat_data VIEW rows into conservative offline diagnostics.

Pure function: no PostgreSQL, network, disk, timers, model inference or BUY.
Schema observed on 2026-10-26: boat_data.races has race_id, race_date,
deadline_at (timestamptz); boat_data.entries has race_id, lane,
racer_no (text), racer_number (integer), 13 STATS columns.
Input rows must have been fetched separately by an explicitly READ-ONLY caller.

Neither created_at/updated_at nor deadline_at authenticate original
pre-decision collection. Never promote this output to paper/forward/BUY.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
from typing import Mapping

from v5.entry_quality_policy import LaneInput, STATS, inspect_race

_RACE_RE = re.compile(r"(20\d{6})_(0[1-9]|1\d|2[0-4])_(0[1-9]|1[0-2])\Z")
_REQUIRED_ENTRY = frozenset(("race_id", "lane", "racer_no", "racer_number", *STATS))
_REQUIRED_RACE = frozenset(("race_id", "race_date", "deadline_at"))
JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class OfflineViewDiagnostic:
    reason: str
    race_id: str = ""
    entry_quality_status: str = ""
    checked_lanes: int = 0
    metadata_shape_consistent: bool = False
    # No official first-sight or independent provenance even after shape PASS.
    original_first_observation_verified: bool = False
    independently_authenticated_source: bool = False
    six_active_starts_confirmed: bool = False
    selection_eligible: bool = False
    forward_eligible: bool = False
    buy_eligible: bool = False


class _InvalidRow(ValueError):
    pass


def _number(value: object) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float, Decimal):
        raise _InvalidRow("non-numeric value")
    try:
        converted = float(value)
    except (ValueError, OverflowError):
        raise _InvalidRow("unrepresentable numeric value") from None
    if not math.isfinite(converted):
        raise _InvalidRow("nonfinite numeric value")
    return converted


def _equipment_number(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not str or not re.fullmatch(r"[0-9]{1,3}", value):
        raise _InvalidRow("noncanonical motor/boat number")
    number = int(value)
    if not 1 <= number <= 999:
        raise _InvalidRow("invalid motor/boat number")
    return number


def _racer_identity(row: Mapping) -> int:
    number = row["racer_number"]
    old_text = row["racer_no"]
    if (type(number) is not int or not 1 <= number <= 9999
            or type(old_text) is not str
            or not re.fullmatch(r"[0-9]{1,4}", old_text)
            or int(old_text) != number):
        raise _InvalidRow("conflicting or absent racer identity")
    return number


def inspect_offline_view_rows(
    race: object, entries: object,
) -> OfflineViewDiagnostic:
    """Diagnose 6-entry VIEW-shaped rows; ALWAYS hard HOLD for actual use.

    Date/deadline consistency validates shape only; a mutable DB VIEW can
    contain information first obtained after the deadline.
    """
    if not isinstance(race, Mapping) or not _REQUIRED_RACE.issubset(race):
        return OfflineViewDiagnostic("RACE_METADATA_SHAPE_HOLD")
    race_id = race["race_id"]
    deadline = race["deadline_at"]
    day = race["race_date"]
    if type(race_id) is not str or not _RACE_RE.fullmatch(race_id):
        return OfflineViewDiagnostic("RACE_METADATA_SHAPE_HOLD")
    try:
        decoded_day = datetime.strptime(race_id[:8], "%Y%m%d").date()
    except ValueError:
        return OfflineViewDiagnostic("RACE_METADATA_SHAPE_HOLD")
    if (type(day) is not date or day != decoded_day or day < date(2025, 7, 1)
            or type(deadline) is not datetime or deadline.tzinfo is None
            or deadline.utcoffset() is None
            or deadline.astimezone(JST).date() != decoded_day):
        return OfflineViewDiagnostic("RACE_METADATA_SHAPE_HOLD", race_id)
    if type(entries) not in (list, tuple) or len(entries) != 6:
        return OfflineViewDiagnostic("SIX_ENTRY_SHAPE_HOLD", race_id)

    lane_inputs = []
    try:
        for row in entries:
            if not isinstance(row, Mapping) or not _REQUIRED_ENTRY.issubset(row):
                raise _InvalidRow("missing required entry field")
            if row["race_id"] != race_id or type(row["lane"]) is not int:
                raise _InvalidRow("race/lane mismatch")
            racer = _racer_identity(row)
            stats = {
                key: (_equipment_number(row[key]) if key in {"motor_no", "boat_no"}
                      else _number(row[key]))
                for key in STATS
            }
            # SQL NULL does not identify official-unreported data. The
            # collector's explicit parse-failure proof is not in this row
            # contract; lack of such evidence never authorizes scoring.
            lane_inputs.append(LaneInput(
                lane=row["lane"], racer_number=racer, stats=stats,
                established_strength_rating=None, missing_evidence=None,
                parser_failed=False,
            ))
    except (_InvalidRow, TypeError, ValueError, KeyError):
        return OfflineViewDiagnostic("ENTRY_TYPE_OR_IDENTITY_HOLD", race_id)

    quality = inspect_race(tuple(lane_inputs))
    if not quality.research_candidate:
        return OfflineViewDiagnostic(
            "ENTRY_QUALITY_HOLD", race_id, quality.status,
            checked_lanes=len(quality.lanes),
        )
    return OfflineViewDiagnostic(
        "VIEW_SHAPE_ONLY_ORIGINAL_ASOF_UNVERIFIED_HOLD",
        race_id, quality.status, checked_lanes=6,
        metadata_shape_consistent=True,
    )
