"""Pure Candidate Discovery V4 contract.

Research only. No external integration or purchase path.
Fixed enrichments:
- Racer Course neutral-missing coefficient = 0.50
- Opponent Pressure first-place-only delta coefficient = 1.0
- Motor2 ticket factor beta = 0.06
- Daily selection = V2 structural-consensus TOP6, top 2 tickets/race
- No EV or absolute-odds gate
"""
from __future__ import annotations

import math
from collections import defaultdict
from itertools import permutations
from typing import Mapping

COURSE_COEF = 0.50
OPPONENT_COEF = 1.0
MOTOR_BETA = 0.06
MOTOR_POS_W = (1.0, 0.6, 0.3)
PROB_TEMP = 2.20
CORE_RACES = 6
CORE_TICKETS = 2
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


def _normalize_tickets(probs: Mapping[str, float]) -> dict[str, float]:
    if len(probs) != 120:
        raise ValueError("120 trifecta probabilities required")
    out = {str(ticket): max(EPS, float(prob)) for ticket, prob in probs.items()}
    if any(not math.isfinite(prob) for prob in out.values()):
        raise ValueError("ticket probabilities must be finite")
    total = sum(out.values())
    if total <= 0:
        raise ValueError("invalid ticket probability mass")
    return {ticket: prob / total for ticket, prob in out.items()}


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


def opponent_adjust_first_probs(
    base_lane_probs: Mapping[int, float],
    opponent_delta: Mapping[int, float] | None,
) -> dict[int, float]:
    if tuple(sorted(base_lane_probs)) != LANES:
        raise ValueError("base_lane_probs must contain lanes 1..6")
    if opponent_delta is None:
        return _normalize(base_lane_probs)
    if tuple(sorted(opponent_delta)) != LANES:
        raise ValueError("opponent_delta must contain lanes 1..6")
    adjusted = {}
    for lane in LANES:
        delta = float(opponent_delta[lane])
        if not math.isfinite(delta):
            raise ValueError("opponent delta must be finite")
        adjusted[lane] = max(EPS, min(0.999, float(base_lane_probs[lane]) + OPPONENT_COEF * delta))
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
    return _normalize_tickets(out)


def head_only_trifecta(
    base_lane_probs: Mapping[int, float],
    adjusted_first_probs: Mapping[int, float],
) -> dict[str, float]:
    """Opponent affects P(first) only; second/third conditionals stay base."""
    base = _normalize(base_lane_probs)
    first = _normalize(adjusted_first_probs)
    out: dict[str, float] = {}
    for a, b, c in permutations(LANES, 3):
        pa = first[a]
        rem_b = 1.0 - base[a]
        pb = base[b] / rem_b
        rem_c = rem_b - base[b]
        out[f"{a}-{b}-{c}"] = pa * pb * (base[c] / rem_c)
    return _normalize_tickets(out)


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
    base_lane = lane_probabilities(raw)
    adjusted_first = opponent_adjust_first_probs(base_lane, opponent_delta)
    probs = head_only_trifecta(base_lane, adjusted_first)
    return motor_adjust(probs, motor_place2)


def structural_metrics(probs: Mapping[str, float]) -> dict[str, float | int]:
    p = _normalize_tickets(probs)
    ranked = sorted(p.items(), key=lambda kv: (-kv[1], kv[0]))
    first_lane: dict[int, float] = defaultdict(float)
    for ticket, prob in p.items():
        first_lane[int(ticket.split("-", 1)[0])] += prob
    heads = sorted(first_lane.items(), key=lambda kv: (-kv[1], kv[0]))
    entropy = -sum(prob * math.log(prob) for prob in p.values()) / math.log(len(p))
    return {
        "head_lane": heads[0][0],
        "head_p1": heads[0][1],
        "head_margin": heads[0][1] - heads[1][1],
        "top3_mass": sum(prob for _, prob in ranked[:3]),
        "concentration": 1.0 - entropy,
    }


def _percentile_rank(rows: list[dict[str, object]], key: str) -> dict[str, float]:
    ordered = sorted(rows, key=lambda row: (-float(row[key]), str(row["race_id"])))
    if len(ordered) <= 1:
        return {str(row["race_id"]): 1.0 for row in ordered}
    return {
        str(row["race_id"]): 1.0 - idx / (len(ordered) - 1)
        for idx, row in enumerate(ordered)
    }


def select_daily(
    distributions: Mapping[str, Mapping[str, float]],
    *,
    race_cap: int = CORE_RACES,
    ticket_count: int = CORE_TICKETS,
) -> list[dict[str, object]]:
    if race_cap < 1 or ticket_count < 1:
        raise ValueError("race_cap and ticket_count must be >= 1")
    rows: list[dict[str, object]] = []
    normalized: dict[str, dict[str, float]] = {}
    for race_id, probs in distributions.items():
        rid = str(race_id)
        normalized[rid] = _normalize_tickets(probs)
        rows.append({"race_id": rid, **structural_metrics(normalized[rid])})
    if not rows:
        return []
    keys = ("head_p1", "head_margin", "top3_mass", "concentration")
    ranks = {key: _percentile_rank(rows, key) for key in keys}
    for row in rows:
        rid = str(row["race_id"])
        row["race_score"] = sum(ranks[key][rid] for key in keys) / len(keys)
    rows.sort(
        key=lambda row: (
            -float(row["race_score"]),
            -float(row["head_p1"]),
            -float(row["top3_mass"]),
            str(row["race_id"]),
        )
    )
    selected = rows[: min(race_cap, len(rows))]
    for idx, row in enumerate(selected, 1):
        rid = str(row["race_id"])
        row["daily_race_rank"] = idx
        row["tickets"] = list(top_tickets(normalized[rid], ticket_count))
    return selected


def top_tickets(probs: Mapping[str, float], n: int = CORE_TICKETS) -> tuple[str, ...]:
    if n < 1:
        raise ValueError("n must be >= 1")
    return tuple(ticket for ticket, _ in sorted(probs.items(), key=lambda kv: (-float(kv[1]), kv[0]))[:n])
