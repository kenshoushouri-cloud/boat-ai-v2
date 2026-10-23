"""Retrospective one-day V5 13-Counter seed from caller-supplied research rows.

Pure Python. No SQL/HTTP/file IO, bets or state promotion. Unlike the genuine
forward freeze/roll-forward pipeline, this is explicitly AFTER-the-fact
research training, not a fabricated frozen prediction or original receipt.
Train on day D only for hypothetical predictions strictly AFTER D.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from v5.offline_prior_day_factor_export import (
    MAP_KEYS, NESTED, PriorDayCounters,
)

_RACE = re.compile(r"^\d{8}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])$")
_SIX = set(range(1, 7))
_MIN = date(2025, 7, 1)


@dataclass(frozen=True)
class RetrospectiveKBoat:
    lane: int
    racer_number: int
    racer_class: str
    exhibition_rank: int
    start_course: int
    finish_position: int
    is_flying: bool | None
    is_late: bool | None


@dataclass(frozen=True)
class RetrospectiveResearchRace:
    race_id: str
    winner_lane: int | None
    boats: tuple[RetrospectiveKBoat, ...]
    result_status: str | None = None
    incident_free_verified: bool | None = None
    refund_boats: tuple[int, ...] | None = None


@dataclass(frozen=True)
class RetrospectiveDayProjection:
    reason: str
    day: date
    state: PriorDayCounters
    accepted_race_ids: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]
    reconstructed_only: bool = field(default=True, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _empty_maps() -> dict:
    c = {key: Counter() for key in MAP_KEYS - NESTED}
    for key in NESTED - {"vc"}:
        c[key] = {lane: Counter() for lane in range(1, 7)}
    c["vc"] = {}
    return c


def _classify(r: object, day: date) -> str | None:
    if type(r) is not RetrospectiveResearchRace or type(r.race_id) is not str:
        return "RACE_TYPE_INVALID"
    if _RACE.fullmatch(r.race_id) is None:
        return "RACE_ID_INVALID"
    try:
        race_day = datetime.strptime(r.race_id[:8], "%Y%m%d").date()
    except ValueError:
        return "RACE_DATE_INVALID"
    if race_day != day:
        return "RACE_NOT_SELECTED_DAY"
    if r.result_status != "OFFICIAL":
        return "POSTRACE_RESULT_NOT_CONFIRMED_OFFICIAL"
    # UNKNOWN is not the same as verified NO incident or NO refund.
    if r.incident_free_verified is not True or r.refund_boats != ():
        return "POSTRACE_INCIDENT_OR_REFUND_NOT_PROVED_CLEAN"
    if type(r.winner_lane) is not int or r.winner_lane not in _SIX:
        return "WINNER_UNKNOWN"
    if type(r.boats) is not tuple or len(r.boats) != 6:
        return "SIX_K_BOATS_REQUIRED"
    if any(type(b) is not RetrospectiveKBoat for b in r.boats):
        return "K_BOAT_TYPE_INVALID"
    b = sorted(r.boats, key=lambda item: item.lane)
    if ({x.lane for x in b} != _SIX
            or {x.start_course for x in b} != _SIX
            or {x.finish_position for x in b} != _SIX):
        return "SIX_LANES_COURSES_FINISHES_INVALID"
    if ({x.exhibition_rank for x in b} != _SIX
            or len({x.racer_number for x in b}) != 6
            or any(type(x.racer_number) is not int or not 1 <= x.racer_number <= 9999
                   or type(x.racer_class) is not str or not x.racer_class.strip()
                   or x.racer_class != x.racer_class.strip().upper()
                   or x.is_flying is not False or x.is_late is not False
                   or type(x.exhibition_rank) is not int
                   or type(x.start_course) is not int
                   or type(x.finish_position) is not int
                   or type(x.lane) is not int for x in b)):
        return "SIX_K_FIELDS_OR_EXHIBITION_INVALID"
    if next(x for x in b if x.lane == r.winner_lane).finish_position != 1:
        return "OFFICIAL_WINNER_K_CONFLICT"
    return None


def project_one_retrospective_day(
    day: date, research_races: tuple[RetrospectiveResearchRace, ...],
    *, history_start: date = _MIN,
) -> RetrospectiveDayProjection:
    """Retrospective single-day Counter *contribution*, not full prior state.

    All data are supplied by an independently audited caller. The supplied
    official/incident/refund claims are not authenticated here; no first-write
    or historical availability proof is possible through this function.
    """
    if (type(day) is not date or day < _MIN
            or type(history_start) is not date
            or not _MIN <= history_start <= day
            or type(research_races) is not tuple):
        raise ValueError("RETROSPECTIVE_DAY_INPUT_INVALID")
    c = _empty_maps()
    accepted: list[str] = []
    excluded: list[tuple[str, str]] = []
    seen = set()
    # Validate candidate shape BEFORE using any postrace winner or finish.
    for r in research_races:
        key = getattr(r, "race_id", "?")
        if type(key) is not str:
            key = "?"
        if key in seen:
            raise ValueError("DUPLICATE_RACE_ID")
        seen.add(key)
        reason = _classify(r, day)
        if reason is not None:
            excluded.append((key, reason))
            continue
        accepted.append(r.race_id)
        winner = r.winner_lane
        venue = r.race_id[9:11]
        b = {row.lane: row for row in r.boats}
        c["lw"][winner] += 1
        c["vc"].setdefault(venue, Counter())[winner] += 1
        c["vn"][venue] += 1
        for lane in range(1, 7):
            boat = b[lane]
            cl, rk = boat.racer_class, str(boat.exhibition_rank)
            c["lcs"][lane][cl] += 1
            c["rks"][(lane, cl, rk)] += 1
            course = boat.start_course
            c["cs"][course] += 1
            c["rcs"][course][boat.racer_number] += 1
            if boat.finish_position <= 3:
                c["ct"][course] += 1
                c["rct"][course][boat.racer_number] += 1
            for opponent in range(1, 7):
                if opponent == lane:
                    continue
                pair = (lane, cl, opponent, b[opponent].racer_class)
                c["ps"][pair] += 1
                if winner == lane:
                    c["pw"][pair] += 1
        w = b[winner]
        c["lcw"][winner][w.racer_class] += 1
        c["rkw"][(winner, w.racer_class, str(w.exhibition_rank))] += 1
    state = PriorDayCounters(
        fitted_through=day,
        history_start=history_start,
        completed_races=len(accepted),
        counters=c,
        source_ref="RETROSPECTIVE_ONE_DAY_UNVERIFIED_" + day.isoformat(),
    )
    return RetrospectiveDayProjection(
        "RETROSPECTIVE_13_COUNTER_ONE_DAY_PROJECTION_NOT_FULL_HISTORY",
        day, state, tuple(sorted(accepted)), tuple(excluded),
    )
