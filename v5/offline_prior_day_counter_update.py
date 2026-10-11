"""Offline incremental prior-day Counter updates matching strong-core research.

Two-phase contract: freeze ALL supplied day predictions (including no-buys)
before passing ANY same-day results to roll_forward_day(). The caller must
independently prove day coverage, evidence provenance and first observation.
This module never runs SQL, settles bets, certifies ROI, or enables BUY.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime

from v5.offline_prior_day_factor_export import MAP_KEYS, NESTED, PriorDayCounters

_ID = re.compile(r"^\d{8}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])$")
_LANES = tuple(range(1, 7))


@dataclass(frozen=True)
class FrozenRace:
    race_id: str
    racer_numbers: tuple[int, ...]       # lane order 1..6
    racer_classes: tuple[str, ...]       # canonical uppercase
    exhibition_ranks: tuple[int, ...]    # lane order 1..6
    selected_tickets: tuple[tuple[int, int, int], ...]  # empty means NO BUY


@dataclass(frozen=True)
class FrozenDay:
    day: date
    races: tuple[FrozenRace, ...]
    baseline_fitted_through: date
    baseline_completed_races: int
    baseline_fingerprint: str
    # Neither independent origin nor complete race-day coverage is established.
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


@dataclass(frozen=True)
class RaceResult:
    race_id: str
    status: str                         # OFFICIAL, VOID, PENDING
    winner_lane: int | None
    has_incident: bool | None            # F/L etc; None means unknown
    refund_boats: tuple[int, ...] | None # None = unknown, NOT no-refund


@dataclass(frozen=True)
class CourseFinish:
    race_id: str
    lane: int
    racer_number: int
    start_course: int | None
    finish_position: int | None


@dataclass(frozen=True)
class DayCounterUpdate:
    state: PriorDayCounters
    all_results: tuple[RaceResult, ...]  # always includes VOID/PENDING/refunds/F/L
    all_course_rows: tuple[CourseFinish, ...]
    fitted_race_ids: tuple[str, ...]
    course_rows_applied: int
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _valid_state(state: object) -> bool:
    if (type(state) is not PriorDayCounters or type(state.fitted_through) is not date
            or type(state.history_start) is not date
            or state.history_start < date(2025, 7, 1)
            or state.history_start > state.fitted_through
            or type(state.completed_races) is not int or state.completed_races < 0
            or type(state.source_ref) is not str or not state.source_ref.strip()
            or not isinstance(state.counters, dict)
            or set(state.counters) != MAP_KEYS):
        return False
    q = state.counters
    for key in MAP_KEYS - NESTED:
        if (type(q[key]) is not Counter
                or any(type(v) is not int or v < 0 for v in q[key].values())):
            return False
    for key in NESTED:
        if not isinstance(q[key], dict):
            return False
        if key != "vc" and any(lane not in q[key] for lane in _LANES):
            return False
        for c in q[key].values():
            if (type(c) is not Counter
                    or any(type(v) is not int or v < 0 for v in c.values())):
                return False
    return (sum(q["lw"].values()) == state.completed_races
            and all(sum(q["lcs"][lane].values()) == state.completed_races
                    and sum(q["lcw"][lane].values()) == q["lw"][lane]
                    for lane in _LANES))


def _fingerprint(state: PriorDayCounters) -> str:
    """Hash value snapshots, not mutable Counter references."""
    def ordered(c: Counter) -> tuple:
        return tuple(sorted(((repr(k), v) for k, v in c.items())))
    parts = [state.history_start.isoformat(), state.fitted_through.isoformat(),
             str(state.completed_races), state.source_ref]
    for key in sorted(MAP_KEYS):
        value = state.counters[key]
        if key in NESTED:
            parts.append(repr((key, tuple(sorted(
                ((repr(k), ordered(v)) for k, v in value.items())))))
        else:
            parts.append(repr((key, ordered(value))))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def freeze_day_predictions(
    state: PriorDayCounters, day: date, predictions: tuple[FrozenRace, ...],
) -> FrozenDay:
    """Freeze the entire caller-supplied day before ANY outcome update."""
    if not _valid_state(state) or type(day) is not date or day <= state.fitted_through:
        raise ValueError("PRIOR_DAY_STATE_REQUIRED")
    if type(predictions) is not tuple or not predictions:
        raise ValueError("DAY_PREDICTIONS_REQUIRED")
    seen = set()
    for race in predictions:
        if (type(race) is not FrozenRace or type(race.race_id) is not str
                or not _ID.fullmatch(race.race_id)
                or race.race_id in seen):
            raise ValueError("RACE_ID_OR_DUPLICATE_INVALID")
        seen.add(race.race_id)
        try:
            race_day = datetime.strptime(race.race_id[:8], "%Y%m%d").date()
        except ValueError as exc:
            raise ValueError("RACE_DATE_INVALID") from exc
        if race_day != day:
            raise ValueError("CROSS_DAY_RACE")
        if (type(race.racer_numbers) is not tuple or len(race.racer_numbers) != 6
                or any(type(v) is not int or not 1 <= v <= 9999
                       for v in race.racer_numbers)
                or len(set(race.racer_numbers)) != 6
                or type(race.racer_classes) is not tuple
                or len(race.racer_classes) != 6
                or any(type(v) is not str or not v or v != v.strip().upper()
                       for v in race.racer_classes)
                or type(race.exhibition_ranks) is not tuple
                or len(race.exhibition_ranks) != 6
                or set(race.exhibition_ranks) != set(_LANES)
                or any(type(v) is not int for v in race.exhibition_ranks)
                or type(race.selected_tickets) is not tuple):
            raise ValueError("SIX_LANE_PREDICTION_INVALID")
        for ticket in race.selected_tickets:
            if (type(ticket) is not tuple or len(ticket) != 3
                    or any(type(v) is not int or v not in _LANES for v in ticket)
                    or len(set(ticket)) != 3):
                raise ValueError("TRIFECTA_TICKET_INVALID")
        if len(set(race.selected_tickets)) != len(race.selected_tickets):
            raise ValueError("DUPLICATE_TICKETS")
    return FrozenDay(day, tuple(sorted(predictions, key=lambda r: r.race_id)),
                     state.fitted_through, state.completed_races, _fingerprint(state))


def roll_forward_day(
    state: PriorDayCounters, frozen: FrozenDay,
    results: tuple[RaceResult, ...],
    course_rows: tuple[CourseFinish, ...] = (),
) -> DayCounterUpdate:
    """Apply all SAME-DAY outcomes only after a complete freeze.

    Training uses only confirmed OFFICIAL races with known no-refund and
    known no-incident evidence. Unknown/VOID/F/L never disappears from
    all_results (the post-prediction selection/settlement population).
    The caller must verify evidence and independently reconcile coverage.
    """
    if (not _valid_state(state) or type(frozen) is not FrozenDay
            or state.fitted_through != frozen.baseline_fitted_through
            or state.completed_races != frozen.baseline_completed_races
            or frozen.day <= state.fitted_through
            or _fingerprint(state) != frozen.baseline_fingerprint):
        raise ValueError("FROZEN_BASELINE_MISMATCH")
    if type(results) is not tuple or type(course_rows) is not tuple:
        raise ValueError("RESULTS_TUPLES_REQUIRED")
    expected = {r.race_id: r for r in frozen.races}
    got = {}
    for result in results:
        if (type(result) is not RaceResult or result.race_id not in expected
                or result.race_id in got
                or result.status not in ("OFFICIAL", "VOID", "PENDING")
                or (result.winner_lane is not None
                    and (type(result.winner_lane) is not int
                         or result.winner_lane not in _LANES))
                or (result.status != "OFFICIAL" and result.winner_lane is not None)
                or (result.has_incident is not None
                    and type(result.has_incident) is not bool)
                or (result.refund_boats is not None
                    and (type(result.refund_boats) is not tuple
                         or any(type(v) is not int or v not in _LANES
                                for v in result.refund_boats)
                         or len(set(result.refund_boats)) != len(result.refund_boats)))):
            raise ValueError("RESULT_INVALID_OR_DUPLICATED")
        got[result.race_id] = result
    if set(got) != set(expected):
        raise ValueError("OUTCOMES_MISSING_FOR_FROZEN_DAY")

    histories: dict[str, dict[int, CourseFinish]] = {}
    for h in course_rows:
        if (type(h) is not CourseFinish or h.race_id not in expected
                or type(h.lane) is not int or h.lane not in _LANES
                or type(h.racer_number) is not int
                or h.racer_number != expected[h.race_id].racer_numbers[h.lane-1]
                or any(x is not None and (type(x) is not int or x not in _LANES)
                       for x in (h.start_course, h.finish_position))):
            raise ValueError("COURSE_ROW_INVALID")
        target = histories.setdefault(h.race_id, {})
        if h.lane in target:
            raise ValueError("COURSE_LANE_DUPLICATE")
        target[h.lane] = h
    if any(len(v) != 6 for v in histories.values()):
        raise ValueError("PARTIAL_COURSE_HISTORY")

    # No mutation occurs until ALL predictions, results and history validate.
    c = deepcopy(dict(state.counters))
    fitted = []
    applied = 0
    for race in frozen.races:
        result = got[race.race_id]
        fit = (result.status == "OFFICIAL"
               and result.winner_lane in _LANES
               and result.has_incident is False
               and result.refund_boats == ())
        if not fit:
            continue
        fitted.append(race.race_id)
        winner = result.winner_lane
        venue = race.race_id[9:11]
        classes = dict(zip(_LANES, race.racer_classes))
        c["lw"][winner] += 1
        c["vc"].setdefault(venue, Counter())[winner] += 1
        c["vn"][venue] += 1
        for lane in _LANES:
            cls, rank = classes[lane], str(race.exhibition_ranks[lane-1])
            c["lcs"][lane][cls] += 1
            c["rks"][(lane, cls, rank)] += 1
        wcls = classes[winner]
        wrank = str(race.exhibition_ranks[winner-1])
        c["lcw"][winner][wcls] += 1
        c["rkw"][(winner, wcls, wrank)] += 1
        for lane in _LANES:
            for opponent in _LANES:
                if opponent == lane:
                    continue
                key = (lane, classes[lane], opponent, classes[opponent])
                c["ps"][key] += 1
                if lane == winner:
                    c["pw"][key] += 1
        hs = histories.get(race.race_id, {})
        if (len(hs) == 6 and
                all(h.start_course in _LANES and h.finish_position in _LANES
                    for h in hs.values()) and
                {h.start_course for h in hs.values()} == set(_LANES)):
            # Same research cs/ct/rcs/rct rule; applied AFTER day predictions.
            for h in hs.values():
                course = h.start_course
                c["cs"][course] += 1
                c["rcs"][course][h.racer_number] += 1
                if h.finish_position <= 3:
                    c["ct"][course] += 1
                    c["rct"][course][h.racer_number] += 1
                applied += 1
    next_state = PriorDayCounters(
        fitted_through=frozen.day, history_start=state.history_start,
        completed_races=state.completed_races + len(fitted),
        counters=c, source_ref=state.source_ref + "|offline-day:" + frozen.day.isoformat())
    return DayCounterUpdate(next_state, tuple(results), tuple(course_rows),
                            tuple(fitted), applied)
