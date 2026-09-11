"""Pure persistence contract for a future Racer Course neutral Forward shadow.

Research only. This module prepares an immutable, DB-ready record but performs no
I/O and contains no database, network, Railway, LINE, or purchase integration.
Actual schema creation, writes, service deployment, and Cron wiring remain an
explicit production-change boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
import math
from zoneinfo import ZoneInfo

from research.racer_course_neutral_shadow_payload import (
    CourseNeutralShadowPayload,
    SHADOW_VERSION,
    V24_PROB_TEMP,
)

JST = ZoneInfo("Asia/Tokyo")
SHADOW_TABLE_NAME = "v2_racer_course_neutral_shadow"
WRITE_POLICY = "FIRST_WRITE_WINS_DO_NOTHING"
TICKET_ORDER_VERSION = "canonical-permutations-1to6-v1"
FORWARD_CUTOFF = time(8, 15)


class CourseNeutralShadowIntegrationError(ValueError):
    pass


@dataclass(frozen=True)
class CourseNeutralShadowRow:
    race_id: str
    race_date: object
    shadow_version: str
    base_version: str
    course_coef: float
    prob_temp: float
    racer_numbers: tuple[int, ...]
    usable_mask: tuple[bool, ...]
    course_top3: tuple[float | None, ...]
    unavailable_reason: tuple[str | None, ...]
    base_raw: tuple[float, ...]
    course_z: tuple[float, ...]
    adjusted_raw: tuple[float, ...]
    ticket_order_version: str
    base_trifecta: tuple[float, ...]
    adjusted_trifecta: tuple[float, ...]
    observed_at: datetime
    write_policy: str

    @property
    def immutable_key(self) -> tuple[str, str]:
        return (self.race_id, self.shadow_version)


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _finite_tuple(values: tuple[float, ...], *, size: int, name: str) -> None:
    if len(values) != size:
        raise CourseNeutralShadowIntegrationError(f"{name} must have {size} values")
    if any(not math.isfinite(float(x)) for x in values):
        raise CourseNeutralShadowIntegrationError(f"{name} must be finite")


def _validate_probability_vector(values: tuple[float, ...], *, name: str) -> None:
    _finite_tuple(values, size=120, name=name)
    if any(float(x) < 0.0 for x in values):
        raise CourseNeutralShadowIntegrationError(f"{name} must be non-negative")
    if abs(sum(float(x) for x in values) - 1.0) > 1e-9:
        raise CourseNeutralShadowIntegrationError(f"{name} must sum to one")


def prepare_shadow_row(
    *,
    payload: CourseNeutralShadowPayload,
    observed_at: datetime,
    deadline_at: datetime,
) -> CourseNeutralShadowRow:
    """Validate a prospective payload and return a first-write-wins row contract.

    This function does not persist anything. It only establishes what a future
    shadow writer would be allowed to persist.
    """
    if payload.shadow_version != SHADOW_VERSION:
        raise CourseNeutralShadowIntegrationError("unexpected shadow version")
    if payload.base_version != "v24":
        raise CourseNeutralShadowIntegrationError("unexpected base version")
    if not payload.race_id.strip():
        raise CourseNeutralShadowIntegrationError("race_id is required")
    if not _aware(observed_at) or not _aware(deadline_at):
        raise CourseNeutralShadowIntegrationError("timestamps must be timezone-aware")

    observed_jst = observed_at.astimezone(JST)
    deadline_jst = deadline_at.astimezone(JST)
    if observed_jst.date() != payload.race_date:
        raise CourseNeutralShadowIntegrationError("observed_at date must equal race_date")
    cutoff = datetime.combine(payload.race_date, FORWARD_CUTOFF, tzinfo=JST)
    if observed_jst > cutoff:
        raise CourseNeutralShadowIntegrationError("observed_at is after 08:15 JST")
    if observed_jst >= deadline_jst:
        raise CourseNeutralShadowIntegrationError("observed_at is at/after race deadline")

    if len(payload.racer_numbers) != 6 or any(int(x) <= 0 for x in payload.racer_numbers):
        raise CourseNeutralShadowIntegrationError("racer_numbers must contain six positive ids")
    if len(payload.usable_mask) != 6:
        raise CourseNeutralShadowIntegrationError("usable_mask must have six values")
    if len(payload.course_top3) != 6 or len(payload.unavailable_reason) != 6:
        raise CourseNeutralShadowIntegrationError("Course evidence arrays must have six values")
    _finite_tuple(payload.base_raw, size=6, name="base_raw")
    _finite_tuple(payload.course_z, size=6, name="course_z")
    _finite_tuple(payload.adjusted_raw, size=6, name="adjusted_raw")
    _validate_probability_vector(payload.base_trifecta, name="base_trifecta")
    _validate_probability_vector(payload.adjusted_trifecta, name="adjusted_trifecta")

    for i in range(6):
        if payload.usable_mask[i]:
            value = payload.course_top3[i]
            if value is None or not math.isfinite(float(value)) or not 0.0 <= float(value) <= 100.0:
                raise CourseNeutralShadowIntegrationError("usable lane requires valid Course Top3")
            if payload.unavailable_reason[i] is not None:
                raise CourseNeutralShadowIntegrationError("usable lane cannot have unavailable reason")
        else:
            if payload.course_top3[i] is not None:
                raise CourseNeutralShadowIntegrationError("unusable lane must not expose Course Top3")
            if not payload.unavailable_reason[i]:
                raise CourseNeutralShadowIntegrationError("unusable lane requires a reason")
            if abs(float(payload.course_z[i])) > 1e-12:
                raise CourseNeutralShadowIntegrationError("unusable lane must have Course z=0")
            if abs(float(payload.adjusted_raw[i]) - float(payload.base_raw[i])) > 1e-12:
                raise CourseNeutralShadowIntegrationError("unusable lane must preserve BASE raw exactly")

    return CourseNeutralShadowRow(
        race_id=payload.race_id,
        race_date=payload.race_date,
        shadow_version=payload.shadow_version,
        base_version=payload.base_version,
        course_coef=float(payload.course_coef),
        prob_temp=V24_PROB_TEMP,
        racer_numbers=tuple(int(x) for x in payload.racer_numbers),
        usable_mask=tuple(bool(x) for x in payload.usable_mask),
        course_top3=payload.course_top3,
        unavailable_reason=payload.unavailable_reason,
        base_raw=payload.base_raw,
        course_z=payload.course_z,
        adjusted_raw=payload.adjusted_raw,
        ticket_order_version=TICKET_ORDER_VERSION,
        base_trifecta=payload.base_trifecta,
        adjusted_trifecta=payload.adjusted_trifecta,
        observed_at=observed_jst,
        write_policy=WRITE_POLICY,
    )
