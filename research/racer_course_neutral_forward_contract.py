"""Pure forward-shadow contract for the fixed Racer Course neutral-missing rule.

Research only: no I/O, DB, Railway, LINE, predictions persistence, or purchases.
The Course coefficient is deliberately not configurable here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import math
from typing import Mapping
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
COURSE_COEF = 0.50
COURSE_CUTOFF = time(8, 15)
EXPECTED_LANES = (1, 2, 3, 4, 5, 6)


class CourseNeutralContractError(ValueError):
    pass


@dataclass(frozen=True)
class CourseLaneEvidence:
    racer_number: int
    lane: int
    course: int
    race_date: date
    top3_rate: float
    created_at: datetime
    deadline_at: datetime


@dataclass(frozen=True)
class CourseNeutralResult:
    adjusted_raw: dict[int, float]
    z_by_lane: dict[int, float]
    usable_lanes: tuple[int, ...]
    unavailable_reasons: dict[int, str]


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _finite(value: object) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _unavailable_reason(
    evidence: CourseLaneEvidence | None,
    *,
    lane: int,
    racer_number: int,
    race_date: date,
) -> str | None:
    if evidence is None:
        return "missing_required_row"
    if evidence.racer_number != racer_number:
        return "racer_mismatch"
    if evidence.lane != lane or evidence.course != lane:
        return "course_lane_mismatch"
    if evidence.race_date != race_date:
        return "wrong_race_date"
    value = _finite(evidence.top3_rate)
    if value is None or not 0.0 <= value <= 100.0:
        return "invalid_top3"
    if not _aware(evidence.created_at) or not _aware(evidence.deadline_at):
        return "naive_timestamp"
    created = evidence.created_at.astimezone(JST)
    deadline = evidence.deadline_at.astimezone(JST)
    cutoff = datetime.combine(race_date, COURSE_CUTOFF, tzinfo=JST)
    if created > cutoff:
        return "created_after_0815"
    if created >= deadline:
        return "created_at_or_after_deadline"
    return None


def apply_course_neutral_rule(
    *,
    base_raw: Mapping[int, float],
    expected_racers: Mapping[int, int],
    race_date: date,
    evidence_by_lane: Mapping[int, CourseLaneEvidence],
) -> CourseNeutralResult:
    """Apply fixed 0.50 Course effect only where exact timing-safe evidence exists.

    Missing/unusable lanes always receive z=0, so BASE raw strength is unchanged.
    """
    if tuple(sorted(base_raw)) != EXPECTED_LANES:
        raise CourseNeutralContractError("base_raw must contain exactly lanes 1..6")
    if tuple(sorted(expected_racers)) != EXPECTED_LANES:
        raise CourseNeutralContractError("expected_racers must contain exactly lanes 1..6")

    normalized_base: dict[int, float] = {}
    for lane in EXPECTED_LANES:
        x = _finite(base_raw[lane])
        if x is None:
            raise CourseNeutralContractError("base_raw must be finite")
        if int(expected_racers[lane]) <= 0:
            raise CourseNeutralContractError("racer number must be positive")
        normalized_base[lane] = x

    reasons: dict[int, str] = {}
    observed: dict[int, float] = {}
    for lane in EXPECTED_LANES:
        evidence = evidence_by_lane.get(lane)
        reason = _unavailable_reason(
            evidence,
            lane=lane,
            racer_number=int(expected_racers[lane]),
            race_date=race_date,
        )
        if reason is not None:
            reasons[lane] = reason
            continue
        assert evidence is not None
        observed[lane] = float(evidence.top3_rate)

    z = {lane: 0.0 for lane in EXPECTED_LANES}
    if len(observed) >= 2:
        values = list(observed.values())
        mean = sum(values) / len(values)
        sd = math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))
        if sd >= 1e-12:
            for lane, value in observed.items():
                z[lane] = (value - mean) / sd

    adjusted = {
        lane: normalized_base[lane] + COURSE_COEF * z[lane]
        for lane in EXPECTED_LANES
    }
    return CourseNeutralResult(
        adjusted_raw=adjusted,
        z_by_lane=z,
        usable_lanes=tuple(sorted(observed)),
        unavailable_reasons=reasons,
    )
