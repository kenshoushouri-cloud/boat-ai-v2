"""Pure Candidate Discovery V4 contract.

Research only. No external integration or purchase path.
Fixed enrichments:
- Racer Course neutral-missing coefficient = 0.50
- Motor2 ticket factor beta = 0.06
- No EV or absolute-odds gate
"""
from __future__ import annotations

import math
from itertools import permutations
from typing import Mapping

COURSE_COEF = 0.50
MOTOR_BETA = 0.06
MOTOR_POS_W = (1.0, 0.6, 0.3)
PROB_TEMP = 2.20
LANES = (1, 2, 3, 4, 5, 6)


def _zscore(values: Mapping[int, float], *, missing_zero: bool) -> dict[int, float]:
    observed = {lane: float(value) for lane, value in values.items() if lane in LANES and math.isfinite(float(value))}
    out = {lane: 0.0 for lane in LANES}
    if len(observed) < 2:
        return out
    xs = list(observed.values())
    mean = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs))
    if sd < 1e-12:
        return out
    for lane, value in observed.items():
        out[lane] = (value - mean) / sd
    if not missing_zero and set(observed) != set(LANES):
        raise ValueError("missing lane not allowed")
    return out


def course_adjust_raw(base_raw: Mapping[int, float], course_top3: Mapping[int, float]) -> dict[int, float]:
    if tuple(sorted(base_raw)) != LANES:
        raise ValueError("base_raw must contain lanes 1..6")
    z = _zscore(course_top3, missing_zero=True)
    return {lane: float(base_raw[lane]) + COURSE_COEF * z[lane] for lane in LANES}


def ticket_probabilities(raw: Mapping[int, float]) -> dict[str, float]:
    if tuple(sorted(raw)) != LANES:
        raise ValueError("raw must contain lanes 1..6")
    weights = {lane: math.exp(float(raw[lane]) / PROB_TEMP) for lane in LANES}
    total = sum(weights.values())
    out: dict[str, float] = {}
    for a, b, c in permutations(LANES, 3):
        pa = weights[a] / total
        rem_b = total - weights[a]
        pb = weights[b] / rem_b
        rem_c = rem_b - weights[b]
        out[f"{a}-{b}-{c}"] = pa * pb * (weights[c] / rem_c)
    z = sum(out.values())
    return {ticket: p / z for ticket, p in out.items()}


def motor_adjust(probs: Mapping[str, float], motor_place2: Mapping[int, float]) -> dict[str, float]:
    if set(motor_place2) != set(LANES):
        return dict(probs)
    z = _zscore(motor_place2, missing_zero=False)
    weighted: dict[str, float] = {}
    for ticket, prob in probs.items():
        a, b, c = (int(x) for x in ticket.split("-"))
        score = MOTOR_POS_W[0] * z[a] + MOTOR_POS_W[1] * z[b] + MOTOR_POS_W[2] * z[c]
        weighted[ticket] = float(prob) * math.exp(MOTOR_BETA * score)
    total = sum(weighted.values())
    return {ticket: value / total for ticket, value in weighted.items()}


def build_v4_distribution(
    *,
    base_raw: Mapping[int, float],
    course_top3: Mapping[int, float],
    motor_place2: Mapping[int, float],
) -> dict[str, float]:
    raw = course_adjust_raw(base_raw, course_top3)
    return motor_adjust(ticket_probabilities(raw), motor_place2)


def top_tickets(probs: Mapping[str, float], n: int = 2) -> tuple[str, ...]:
    if n < 1:
        raise ValueError("n must be >= 1")
    return tuple(ticket for ticket, _ in sorted(probs.items(), key=lambda kv: (-float(kv[1]), kv[0]))[:n])
