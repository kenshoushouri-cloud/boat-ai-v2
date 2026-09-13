"""Pure late Bao corroboration contract for Candidate Discovery.

This layer never removes a V4 race or ticket. It only computes a timing-safe
late market+Motor2+exhibition distribution and reports whether its top tickets
corroborate the already-selected V4 tickets.

Frozen research coefficients:
- Motor2 beta = 0.06
- Exhibition-time rank beta = 0.06
- ticket position weights = 1.0 / 0.6 / 0.3

No expected-value calculation and no absolute-odds eligibility gate.
"""
from __future__ import annotations

import math
from itertools import permutations
from typing import Mapping, Sequence

MOTOR_BETA = 0.06
EXHIBITION_BETA = 0.06
POS_W = (1.0, 0.6, 0.3)
LANES = (1, 2, 3, 4, 5, 6)
TICKETS = tuple(f"{a}-{b}-{c}" for a, b, c in permutations(LANES, 3))
EPS = 1e-12


def _zscore(values: Mapping[int, float]) -> dict[int, float]:
    if set(values) != set(LANES):
        raise ValueError("six lanes required")
    xs = {lane: float(values[lane]) for lane in LANES}
    if any(not math.isfinite(x) for x in xs.values()):
        raise ValueError("finite values required")
    mean = sum(xs.values()) / 6.0
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs.values()) / 6.0)
    if sd < 1e-12:
        raise ValueError("nonzero variance required")
    return {lane: (x - mean) / sd for lane, x in xs.items()}


def _ticket_scores(z: Mapping[int, float]) -> dict[str, float]:
    out = {}
    for ticket in TICKETS:
        a, b, c = (int(x) for x in ticket.split("-"))
        out[ticket] = POS_W[0] * z[a] + POS_W[1] * z[b] + POS_W[2] * z[c]
    return out


def devig_market(odds: Mapping[str, float]) -> dict[str, float]:
    if set(odds) != set(TICKETS):
        raise ValueError("complete 120-ticket odds required")
    inv = {}
    for ticket in TICKETS:
        odd = float(odds[ticket])
        if not math.isfinite(odd) or odd <= 1.0:
            raise ValueError("all odds must be finite and > 1.0")
        inv[ticket] = 1.0 / odd
    total = sum(inv.values())
    return {ticket: value / total for ticket, value in inv.items()}


def bao_distribution(
    *,
    odds: Mapping[str, float],
    motor_place2: Mapping[int, float],
    exhibition_time_rank: Mapping[int, int],
) -> dict[str, float]:
    q = devig_market(odds)
    motor_z = _zscore({lane: float(motor_place2[lane]) for lane in LANES})
    ranks = {lane: int(exhibition_time_rank[lane]) for lane in LANES}
    if set(ranks.values()) != set(LANES):
        raise ValueError("exhibition ranks must be a permutation of 1..6")
    exhibition_z = _zscore({lane: -float(ranks[lane]) for lane in LANES})
    motor_score = _ticket_scores(motor_z)
    exhibition_score = _ticket_scores(exhibition_z)
    weighted = {
        ticket: q[ticket]
        * math.exp(MOTOR_BETA * motor_score[ticket] + EXHIBITION_BETA * exhibition_score[ticket])
        for ticket in TICKETS
    }
    total = sum(weighted.values())
    if total <= 0 or not math.isfinite(total):
        raise ValueError("invalid adjusted probability mass")
    return {ticket: value / total for ticket, value in weighted.items()}


def top_tickets(probs: Mapping[str, float], n: int = 2) -> tuple[str, ...]:
    if n < 1:
        raise ValueError("n must be >= 1")
    return tuple(ticket for ticket, _ in sorted(probs.items(), key=lambda kv: (-float(kv[1]), kv[0]))[:n])


def corroboration(
    *,
    v4_tickets: Sequence[str],
    bao_probs: Mapping[str, float],
    bao_top_n: int = 2,
) -> dict[str, object]:
    v4 = tuple(dict.fromkeys(str(ticket) for ticket in v4_tickets))
    bao = top_tickets(bao_probs, bao_top_n)
    overlap = tuple(ticket for ticket in v4 if ticket in set(bao))
    return {
        "v4_tickets": v4,
        "late_bao_top_tickets": bao,
        "overlap_tickets": overlap,
        "overlap_count": len(overlap),
        "corroborated": bool(overlap),
        "candidate_removed": False,
        "purchase_action": False,
    }
