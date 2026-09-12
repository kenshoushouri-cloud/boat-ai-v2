"""Pure Candidate Discovery V4 contract.

Research only. No external integration or purchase path.
Fixed enrichments:
- Racer Course neutral-missing coefficient = 0.50
- Opponent Pressure lane-probability delta coefficient = 1.0
- Motor2 ticket factor beta = 0.06
- No EV or absolute-odds gate
"""
from __future__ import annotations

import math
from itertools import permutations
from typing import Mapping

COURSE_COEF = 0.50
OPPONENT_COEF = 1.0
MOTOR_BETA = 0.06
MOTOR_POS_W = (1.0, 0.6, 0.3)
PROB_TEMP = 2.20
LANES = (1, 2, 3, 4, 5, 6)
EPS = 1e-12


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


def _normalize(values: Mapping[int, float]) -> dict[int, float]:
    ys = {lane: max(EPS, float(values[lane])) for lane in LANES}
    total = sum(ys.values())
    if total <= 0 or not math.isfinite(total):
        raise ValueError("invalid probability mass")
    return {lane: value / total for lane, value in ys.items()}


def course_adjust_raw(base_raw: Mapping[int, float], course_top3: Mapping[int, float]) -> dict[int, float]:
    if tuple(sorted(base_raw)) != LANES:
        raise ValueError("base_raw must contain lanes 1..6")
    z = _zscore(course_top3, missing_zero=True)
    return {lane: float(base_raw[lane]) + COURSE_COEF * z[lane] for lane in LANES}


def lane_probabilities(raw: Mapping[int, float]) -> dict[int, float]:
    if tuple(sorted(raw)) != LANES:
        raise ValueError("raw must contain lanes 1..6")
    weights = {lane: math.exp(float(raw[lane]) / PROB_TEMP) for lane in LANES}
    return _normalize(weights)


def opponent_adjust_lane_probs(
    lane_probs: Mapping[int, float],
    opponent_delta: Mapping[int, float] | None,
) -> dict[int, float]:
    if tuple(sorted(lane_probs)) != LANES:
        raise ValueError("lane_probs must contain lanes 1..6")
    if opponent_delta is None:
        return _normalize(lane_probs)
    if tuple(sorted(opponent_delta)) != LANES:
        raise ValueError("opponent_delta must contain lanes 1..6")
    adjusted = {}
    for lane in LANES:
        delta = float(opponent_delta[lane])
        if not math.isfinite(delta):
            raise ValueError("opponent delta must be finite")
        adjusted[lane] = max(EPS, min(0.999, float(lane_probs[lane]) + OPPONENT_COEF * delta))
    return _normalize(adjusted)


def pl_trifecta(lane_probs: Mapping[int, float]) -> dict[str, float]:
    probs = _normalize(lane_probs)
    out: dict[str, float] = {}
    for a, b, c in permutations(LANES, 3):
        pa = probs[a]
        rem_b = 1.0 - probs[a]
        pb = probs[b] / rem_b
        rem_c = rem_b - probs[b]
        out[f"{a}-{b}-{c}"] = pa * pb * (probs[c] / rem_c)
    z = sum(out.values())
    return {ticket: p / z for ticket, p in out.items()}


def ticket_probabilities(raw: Mapping[int, float]) -> dict[str, float]:
    return pl_trifecta(lane_probabilities(raw))


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
    opponent_delta: Mapping[int, float] | None = None,
) -> dict[str, float]:
    raw = course_adjust_raw(base_raw, course_top3)
    lane_probs = opponent_adjust_lane_probs(lane_probabilities(raw), opponent_delta)
    return motor_adjust(pl_trifecta(lane_probs), motor_place2)


def top_tickets(probs: Mapping[str, float], n: int = 2) -> tuple[str, ...]:
    if n < 1:
        raise ValueError("n must be >= 1")
    return tuple(ticket for ticket, _ in sorted(probs.items(), key=lambda kv: (-float(kv[1]), kv[0]))[:n])
