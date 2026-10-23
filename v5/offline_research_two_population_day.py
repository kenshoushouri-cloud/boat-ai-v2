"""Research-only daily V5 Counter source adapter: separate two populations.

Full six-lane/model-feature fit examples NEED exhibition ranks. Racer-course
history can include an otherwise clean official K race even without an exhibition
snapshot. This prevents discarding useful past course evidence merely because
that race was outside the forward-exhibition collection window.

All source claims are caller-provided and UNVERIFIED. It does not read the DB,
authenticate first capture, create a complete historical baseline, or allow BUY.
Postrace evidence may gate RETROSPECTIVE fitting but never pre-race selection.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Iterable

from v5.offline_prior_day_factor_export import NESTED, PriorDayCounters
from v5.offline_retrospective_counter_seed import (
    RetrospectiveResearchRace, project_one_retrospective_day,
)

_ID = re.compile(r"^\d{8}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])$")
_SIX = set(range(1, 7))


@dataclass(frozen=True)
class CourseKBoat:
    lane: int
    racer_number: int
    start_course: int | None
    finish_position: int | None
    is_flying: bool | None
    is_late: bool | None


@dataclass(frozen=True)
class CourseHistoryRace:
    race_id: str
    boats: tuple[CourseKBoat, ...]
    result_status: str | None  # independently evidenced by caller; not certified
    incident_free_verified: bool | None
    refund_boats: tuple[int, ...] | None


@dataclass(frozen=True)
class SplitDayProjection:
    day: date
    state: PriorDayCounters
    fit_race_ids: tuple[str, ...]
    course_race_ids: tuple[str, ...]
    fit_excluded: tuple[tuple[str, str], ...]
    course_excluded: tuple[tuple[str, str], ...]
    reconstructed_only: bool = field(default=True, init=False)
    first_observation_verified: bool = field(default=False, init=False)
    source_state_independently_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _course_reason(r: object, day: date) -> str | None:
    if type(r) is not CourseHistoryRace or type(r.race_id) is not str:
        return "K_SOURCE_TYPE_INVALID"
    if _ID.fullmatch(r.race_id) is None:
        return "K_RACE_ID_INVALID"
    try:
        if datetime.strptime(r.race_id[:8], "%Y%m%d").date() != day:
            return "K_CROSS_DAY"
    except ValueError:
        return "K_RACE_DATE_INVALID"
    if r.result_status != "OFFICIAL":
        return "K_RESULT_NOT_CONFIRMED"
    if r.incident_free_verified is not True or r.refund_boats != ():
        return "K_INCIDENT_OR_REFUND_UNKNOWN_OR_PRESENT"
    if type(r.boats) is not tuple or len(r.boats) != 6:
        return "K_SIX_BOATS_REQUIRED"
    if any(type(b) is not CourseKBoat for b in r.boats):
        return "K_BOAT_SHAPE_INVALID"
    if ({b.lane for b in r.boats} != _SIX
            or {b.start_course for b in r.boats} != _SIX
            or {b.finish_position for b in r.boats} != _SIX):
        return "K_LANE_COURSE_OR_FINISH_NOT_SIX"
    if (len({b.racer_number for b in r.boats}) != 6
            or any(type(b.lane) is not int
                   or type(b.racer_number) is not int
                   or not 1 <= b.racer_number <= 9999
                   or type(b.start_course) is not int
                   or type(b.finish_position) is not int
                   or b.is_flying is not False
                   or b.is_late is not False for b in r.boats)):
        return "K_RACER_OR_FLAGS_INVALID"
    return None


def project_two_population_day(
    day: date,
    model_fit_races: tuple[RetrospectiveResearchRace, ...],
    course_history_races: tuple[CourseHistoryRace, ...],
    *,
    history_start: date = date(2025, 7, 1),
) -> SplitDayProjection:
    """Generate only day D contributions, safe to use AFTER D in research.

    The model-fit course counters are deliberately REPLACED, not added, with
    a separate K-source course population; the same race must be counted once.
    Independent verification and full-day history coverage are caller duties.
    """
    if type(course_history_races) is not tuple:
        raise ValueError("K_HISTORY_TUPLE_REQUIRED")
    fitted = project_one_retrospective_day(
        day, model_fit_races, history_start=history_start
    )
    # This adapter must not certify an incomplete K course population.
    # We return accepted/excluded reasons, never claim full-day coverage.
    seen = set()
    accepted: list[str] = []
    excluded: list[tuple[str, str]] = []
    cs, ct = Counter(), Counter()
    rcs = {course: Counter() for course in range(1, 7)}
    rct = {course: Counter() for course in range(1, 7)}
    for r in course_history_races:
        race_id = getattr(r, "race_id", None)
        if type(race_id) is not str:
            raise ValueError("K_RACE_ID_TYPE_INVALID")
        if race_id in seen:
            raise ValueError("DUPLICATE_K_RACE")
        seen.add(race_id)
        reason = _course_reason(r, day)
        if reason is not None:
            excluded.append((race_id, reason))
            continue
        accepted.append(race_id)
        for b in r.boats:
            course = b.start_course
            cs[course] += 1
            rcs[course][b.racer_number] += 1
            if b.finish_position <= 3:
                ct[course] += 1
                rct[course][b.racer_number] += 1

    c = dict(fitted.state.counters)
    # Replace four categories; do not double count overlapping fit/K races.
    c.update(cs=cs, ct=ct, rcs=rcs, rct=rct)
    state = replace(
        fitted.state,
        counters=c,
        source_ref=(
            "RETROSPECTIVE_SPLIT_TWO_POPULATIONS_UNVERIFIED_"
            + day.isoformat()
        ),
    )
    return SplitDayProjection(
        day=day, state=state,
        fit_race_ids=fitted.accepted_race_ids,
        course_race_ids=tuple(sorted(accepted)),
        fit_excluded=fitted.excluded,
        course_excluded=tuple(excluded),
    )
