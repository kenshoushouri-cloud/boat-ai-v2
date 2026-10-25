"""Pure safety gate for the eight verified October 2026 K-detail gaps.

This module has NO database, HTTP, file-system, timer or write operations.
Use it before any subsequent official-K per-day INSERT. It never approves
production route changes or a backfill in the absence of recovery evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Any

EXPECTED_RACES = {
    "2026-10-15": 156,
    "2026-10-16": 156,
    "2026-10-17": 168,
    "2026-10-21": 144,
    "2026-10-22": 168,
    "2026-10-23": 168,
    "2026-10-24": 168,
    "2026-10-25": 167,
}
CANCELLED_IDS = {
    "2026-10-21": frozenset(
        f"20261021_03_{n:02d}" for n in range(1, 13)
    ),
    "2026-10-25": frozenset({"20261025_20_12"}),
}
EXPECTED_TOTAL_RACES = 1295
EXPECTED_TOTAL_LANES = 7770

assert sum(EXPECTED_RACES.values()) == EXPECTED_TOTAL_RACES


@dataclass(frozen=True)
class KDayGate:
    date: str
    known_races: int
    k_races: int
    expected_lanes: int
    cancelled_race_ids: tuple[str, ...]
    status: str = "K_DAY_PURE_VALIDATION_PASS_NOT_BACKFILLED"


def validate_day(
    day: str,
    known: Mapping[str, Mapping[str, Any]],
    parsed: Sequence[Mapping[str, Any]],
) -> KDayGate:
    """Validate official six-lane detail and exact known cancellation exceptions.

    known: {race_id: {result_status, trifecta_ticket, trifecta_payout_yen}}
    parsed: output of audit_k_day_all_pg.parse_section after each official K GET
    Raises ValueError on any mismatch. No mutation/IO.
    """
    if day not in EXPECTED_RACES:
        raise ValueError("HOLD: day not in verified K repair scope")
    prefix = day.replace("-", "") + "_"
    if not known or len(known) > 288:
        raise ValueError("HOLD: missing or implausible known races")
    known_ids = set(known)
    if any(not rid.startswith(prefix) for rid in known_ids):
        raise ValueError("HOLD: DB race date mismatch")
    if len(parsed) != EXPECTED_RACES[day]:
        raise ValueError("HOLD: official K race count changed")
    ids = []
    for race in parsed:
        rid = str(race.get("race_id", ""))
        ids.append(rid)
        if not rid.startswith(prefix):
            raise ValueError("HOLD: K race date mismatch")
        if race.get("parse_failed_candidate_lines"):
            raise ValueError("HOLD: K parser incomplete")
        entries = race.get("entries")
        if not isinstance(entries, (list, tuple)) or len(entries) != 6:
            raise ValueError("HOLD: K not six lanes")
        if {str(e.get("lane")) for e in entries} != set("123456"):
            raise ValueError("HOLD: K duplicate/missing lanes")
    if len(set(ids)) != len(ids):
        raise ValueError("HOLD: duplicate K race ID")
    k_ids = set(ids)
    if k_ids - known_ids:
        raise ValueError("HOLD: K race absent from original DB")
    absent = known_ids - k_ids
    expected_absent = CANCELLED_IDS.get(day, frozenset())
    if absent != expected_absent:
        raise ValueError("HOLD: unexpected absent/K-only race")
    for rid in absent:
        row = known[rid]
        if (str(row.get("result_status", "")).lower() != "cancelled"
                or row.get("trifecta_ticket") is not None
                or row.get("trifecta_payout_yen") != 0):
            raise ValueError("HOLD: missing race not confirmed cancelled")
    return KDayGate(
        day, len(known), len(ids), len(ids) * 6, tuple(sorted(absent))
    )


def validate_complete_batch(gates: Sequence[KDayGate]) -> bool:
    if {x.date for x in gates} != set(EXPECTED_RACES):
        raise ValueError("HOLD: missing or duplicated repair dates")
    if len(gates) != len(EXPECTED_RACES):
        raise ValueError("HOLD: duplicate repair date")
    if sum(x.k_races for x in gates) != EXPECTED_TOTAL_RACES:
        raise ValueError("HOLD: expected K race count mismatch")
    if sum(x.expected_lanes for x in gates) != EXPECTED_TOTAL_LANES:
        raise ValueError("HOLD: expected six-lane count mismatch")
    return True
