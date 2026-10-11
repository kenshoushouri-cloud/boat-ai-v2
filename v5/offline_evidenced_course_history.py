"""Offline-only result-evidenced course-history update after a full day freeze.

The original research hday is independent of the scored race subset.
This adapter calls roll_forward_day with NO course_rows, then records course
counts exactly once from independently supplied post-race evidence for both
scored and unscored-feature races. Unknown provenance is never certified.
No DB, no forward predictions, no bet authorization, no ROI claims.
"""
from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import date, datetime

from v5.offline_prior_day_factor_export import PriorDayCounters
from v5.offline_prior_day_counter_update import (
    DayCounterUpdate, FrozenDay, RaceResult, roll_forward_day,
)

_RID = re.compile(r"^\d{8}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])$")
_NORMAL = frozenset(f"{i:02d}" for i in range(1, 7))
_HISTORY = ("cs", "ct", "rcs", "rct")


@dataclass(frozen=True)
class EvidencedCourseRow:
    lane: int
    racer_number: int | None
    start_course: int | None
    finish_position: int | None
    finish_status: str | None
    is_flying: bool | None
    is_late: bool | None


@dataclass(frozen=True)
class EvidencedCourseRace:
    race_id: str
    result_status: str | None
    race_status: str | None
    official_result_verified: bool
    official_k_void_checked_clear: bool | None
    refund_boats: tuple[int, ...] | None
    rows: tuple[EvidencedCourseRow, ...]
    source_ref: str


@dataclass(frozen=True)
class CourseHistoryAudit:
    day_update: DayCounterUpdate
    state: PriorDayCounters
    all_course_evidence: tuple[EvidencedCourseRace, ...]
    applied_race_ids: tuple[str, ...]
    held_races: tuple[tuple[str, str], ...]
    skipped_invalid_rows: tuple[tuple[str, int], ...]
    increments: dict[str, int]
    evidence_provenance_independently_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _race_id_date(race_id: object) -> date:
    if type(race_id) is not str or not _RID.fullmatch(race_id):
        raise ValueError("HISTORY_RACE_ID_INVALID")
    try:
        return datetime.strptime(race_id[:8], "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError("HISTORY_RACE_DATE_INVALID") from exc


def _valid_refunds(refunds: object) -> bool:
    return (type(refunds) is tuple
            and all(type(x) is int and 1 <= x <= 6 for x in refunds)
            and len(set(refunds)) == len(refunds))


def apply_evidenced_course_history(
    prior: PriorDayCounters,
    frozen: FrozenDay,
    results: tuple[RaceResult, ...],
    histories: tuple[EvidencedCourseRace, ...],
) -> CourseHistoryAudit:
    """Research-only atomic day transition.

    Completeness/authenticity of caller-supplied evidence is NOT verified here.
    A zero-prediction day cannot be sealed using FrozenDay, so fails closed.
    All frozen predictions must exist BEFORE passing the day's results.
    """
    # Run the existing day barrier and primary fit ONCE, with zero course rows.
    base = roll_forward_day(prior, frozen, results, ())
    if type(histories) is not tuple:
        raise ValueError("HISTORY_TUPLE_REQUIRED")
    by_result = {r.race_id: r for r in base.all_results}
    seen = set()
    held = []
    rejected = []
    applied = []
    increments = {key: 0 for key in _HISTORY}
    counts = deepcopy(dict(base.state.counters))

    # Validate the ENTIRE batch before changing ANY local Counter.
    for race in histories:
        if type(race) is not EvidencedCourseRace:
            raise ValueError("HISTORY_RACE_TYPE_INVALID")
        if _race_id_date(race.race_id) != frozen.day:
            raise ValueError("HISTORY_DAY_MISMATCH")
        if race.race_id in seen:
            raise ValueError("DUPLICATE_HISTORY_RACE")
        seen.add(race.race_id)
        if type(race.source_ref) is not str or not race.source_ref.strip():
            raise ValueError("HISTORY_SOURCE_REF_REQUIRED")
        if type(race.rows) is not tuple or len(race.rows) != 6:
            raise ValueError("SIX_HISTORY_RESULT_ROWS_REQUIRED")
        if (type(race.official_result_verified) is not bool
                or race.official_k_void_checked_clear is not None
                and type(race.official_k_void_checked_clear) is not bool):
            raise ValueError("HISTORY_EVIDENCE_FLAG_INVALID")
        if race.refund_boats is not None and not _valid_refunds(race.refund_boats):
            raise ValueError("HISTORY_REFUNDS_INVALID")
        lanes = set()
        for entry in race.rows:
            if type(entry) is not EvidencedCourseRow:
                raise ValueError("HISTORY_ROW_TYPE_INVALID")
            if type(entry.lane) is not int or entry.lane not in range(1, 7):
                raise ValueError("HISTORY_LANE_INVALID")
            if entry.lane in lanes:
                raise ValueError("DUPLICATE_HISTORY_LANE")
            lanes.add(entry.lane)
        if lanes != set(range(1, 7)):
            raise ValueError("INCOMPLETE_HISTORY_LANES")

    for race in sorted(histories, key=lambda r: r.race_id):
        # No status/null/refund inference; original incident check must
        # receive all six normal result entries with explicit false flags.
        status_ok = (race.result_status == "OFFICIAL"
                     and race.race_status == "OFFICIAL"
                     and race.official_result_verified is True
                     and race.official_k_void_checked_clear is True)
        six_clean = all(
            row.finish_status in _NORMAL
            and row.is_flying is False
            and row.is_late is False for row in race.rows
        )
        known = by_result.get(race.race_id)
        consistent = (known is None or (
            known.status == "OFFICIAL" and known.has_incident is False
            and known.refund_boats == ()
        ))
        if not status_ok:
            held.append((race.race_id, "OFFICIAL_OR_VOID_EVIDENCE_MISSING"))
            continue
        if race.refund_boats != () or not consistent:
            held.append((race.race_id, "REFUND_OR_FROZEN_RESULT_UNRESOLVED"))
            continue
        if not six_clean:
            held.append((race.race_id, "INCIDENT_OR_SIX_RESULT_EVIDENCE_MISSING"))
            continue
        # Verify row-to-frozen racer identity whenever a frozen prediction
        # exists; never silently attach another racer to a prediction.
        frozen_race = next((r for r in frozen.races if r.race_id == race.race_id), None)
        if frozen_race is not None and any(
            row.racer_number != frozen_race.racer_numbers[row.lane - 1]
            for row in race.rows
        ):
            held.append((race.race_id, "FROZEN_RACER_IDENTITY_MISMATCH"))
            continue
        valid_rows = [
            row for row in race.rows
            if type(row.racer_number) is int and row.racer_number > 0
            and type(row.start_course) is int and 1 <= row.start_course <= 6
            and type(row.finish_position) is int and 1 <= row.finish_position <= 6
        ]
        # Unlike research, fail closed on contradictory duplicate course/finish
        # information. Incomplete numeric rows may contribute individually.
        if (len({r.racer_number for r in valid_rows}) != len(valid_rows)
                or len({r.start_course for r in valid_rows}) != len(valid_rows)
                or len({r.finish_position for r in valid_rows}) != len(valid_rows)):
            held.append((race.race_id, "DUPLICATE_VALID_COURSE_OR_FINISH"))
            continue
        for row in race.rows:
            if row not in valid_rows:
                rejected.append((race.race_id, row.lane))
        for row in valid_rows:
            course = row.start_course
            racer = row.racer_number
            counts["cs"][course] += 1
            counts["rcs"][course][racer] += 1
            increments["cs"] += 1
            increments["rcs"] += 1
            if row.finish_position <= 3:
                counts["ct"][course] += 1
                counts["rct"][course][racer] += 1
                increments["ct"] += 1
                increments["rct"] += 1
        if valid_rows:
            applied.append(race.race_id)
        else:
            held.append((race.race_id, "NO_VALID_NUMERIC_COURSE_ROWS"))

    state = replace(base.state, counters=counts,
                    source_ref=base.state.source_ref + "|evidenced-course-history")
    return CourseHistoryAudit(
        base, state, tuple(histories), tuple(applied), tuple(held),
        tuple(rejected), increments,
    )
