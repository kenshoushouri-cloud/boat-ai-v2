"""Pure immutable payload builder for a future Course-neutral Forward shadow.

Research only. No database, network, Railway, LINE, or purchase dependency.
The probability temperature is frozen to current v24 research baseline 2.20.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import permutations
import math
from typing import Mapping

from research.racer_course_neutral_forward_contract import (
    COURSE_COEF,
    CourseLaneEvidence,
    apply_course_neutral_rule,
)

V24_PROB_TEMP = 2.20
SHADOW_VERSION = "course-neutral-missing-v1"
CANONICAL_TICKETS = tuple("-".join(map(str, xs)) for xs in permutations(range(1, 7), 3))


class CourseNeutralPayloadError(ValueError):
    pass


@dataclass(frozen=True)
class CourseNeutralShadowPayload:
    race_id: str
    race_date: date
    shadow_version: str
    base_version: str
    course_coef: float
    racer_numbers: tuple[int, ...]
    usable_mask: tuple[bool, ...]
    course_top3: tuple[float | None, ...]
    unavailable_reason: tuple[str | None, ...]
    base_raw: tuple[float, ...]
    course_z: tuple[float, ...]
    adjusted_raw: tuple[float, ...]
    base_trifecta: tuple[float, ...]
    adjusted_trifecta: tuple[float, ...]


def trifecta_probabilities(raw: Mapping[int, float]) -> dict[str, float]:
    if tuple(sorted(raw)) != (1, 2, 3, 4, 5, 6):
        raise CourseNeutralPayloadError("raw strengths must contain lanes 1..6")
    vals: dict[int, float] = {}
    for lane in range(1, 7):
        try:
            x = float(raw[lane])
        except (TypeError, ValueError) as exc:
            raise CourseNeutralPayloadError("raw strengths must be numeric") from exc
        if not math.isfinite(x):
            raise CourseNeutralPayloadError("raw strengths must be finite")
        vals[lane] = x

    # Shift before exponentiation for numerical stability without changing ratios.
    scaled = {lane: vals[lane] / V24_PROB_TEMP for lane in range(1, 7)}
    shift = max(scaled.values())
    weights = {lane: math.exp(scaled[lane] - shift) for lane in range(1, 7)}
    total = sum(weights.values())
    if not math.isfinite(total) or total <= 0:
        raise CourseNeutralPayloadError("invalid lane weight total")

    out: dict[str, float] = {}
    for a, b, c in permutations(range(1, 7), 3):
        rem_b = total - weights[a]
        rem_c = rem_b - weights[b]
        if rem_b <= 0 or rem_c <= 0:
            raise CourseNeutralPayloadError("invalid sequential probability denominator")
        p = (weights[a] / total) * (weights[b] / rem_b) * (weights[c] / rem_c)
        out[f"{a}-{b}-{c}"] = p

    z = sum(out.values())
    if len(out) != 120 or not math.isfinite(z) or z <= 0:
        raise CourseNeutralPayloadError("invalid trifecta probability vector")
    normalized = {ticket: out[ticket] / z for ticket in CANONICAL_TICKETS}
    if abs(sum(normalized.values()) - 1.0) > 1e-12:
        raise CourseNeutralPayloadError("trifecta probability vector does not sum to one")
    return normalized


def build_shadow_payload(
    *,
    race_id: str,
    race_date: date,
    base_raw: Mapping[int, float],
    expected_racers: Mapping[int, int],
    evidence_by_lane: Mapping[int, CourseLaneEvidence],
) -> CourseNeutralShadowPayload:
    if not race_id.strip():
        raise CourseNeutralPayloadError("race_id is required")
    result = apply_course_neutral_rule(
        base_raw=base_raw,
        expected_racers=expected_racers,
        race_date=race_date,
        evidence_by_lane=evidence_by_lane,
    )
    base_probs = trifecta_probabilities(base_raw)
    adjusted_probs = trifecta_probabilities(result.adjusted_raw)

    top3: list[float | None] = []
    for lane in range(1, 7):
        evidence = evidence_by_lane.get(lane)
        if lane in result.usable_lanes and evidence is not None:
            top3.append(float(evidence.top3_rate))
        else:
            top3.append(None)

    return CourseNeutralShadowPayload(
        race_id=race_id,
        race_date=race_date,
        shadow_version=SHADOW_VERSION,
        base_version="v24",
        course_coef=COURSE_COEF,
        racer_numbers=tuple(int(expected_racers[lane]) for lane in range(1, 7)),
        usable_mask=tuple(lane in result.usable_lanes for lane in range(1, 7)),
        course_top3=tuple(top3),
        unavailable_reason=tuple(result.unavailable_reasons.get(lane) for lane in range(1, 7)),
        base_raw=tuple(float(base_raw[lane]) for lane in range(1, 7)),
        course_z=tuple(float(result.z_by_lane[lane]) for lane in range(1, 7)),
        adjusted_raw=tuple(float(result.adjusted_raw[lane]) for lane in range(1, 7)),
        base_trifecta=tuple(base_probs[ticket] for ticket in CANONICAL_TICKETS),
        adjusted_trifecta=tuple(adjusted_probs[ticket] for ticket in CANONICAL_TICKETS),
    )
