"""Pure bet-type comparison contract for Candidate Discovery.

Research only. Derives 2-ren-tan (exacta) and 3-ren-puku (trio) probabilities
from the same 120-ticket trifecta distribution. No market odds, payout data,
database, network, LINE, or purchase integration.

The comparison grid is frozen before outcome evaluation:
- ticket types: trifecta / exacta / trio
- fixed selections: top 1 / 2 / 3 / 5 tickets
- cumulative-probability selections: 20% / 35% / 50%, capped at 12 tickets
- flat stake: 100 JPY per selected ticket
"""
from __future__ import annotations

from collections import defaultdict
from itertools import permutations
from typing import Mapping

BET_TYPES = ("trifecta", "exacta", "trio")
FIXED_POINT_COUNTS = (1, 2, 3, 5)
COVERAGE_TARGETS = (0.20, 0.35, 0.50)
COVERAGE_MAX_TICKETS = 12
STAKE_PER_TICKET_YEN = 100
LANES = (1, 2, 3, 4, 5, 6)


def _normalize(probs: Mapping[str, float]) -> dict[str, float]:
    vals = {str(k): max(0.0, float(v)) for k, v in probs.items()}
    total = sum(vals.values())
    if total <= 0:
        raise ValueError("probability mass must be positive")
    return {k: v / total for k, v in vals.items()}


def validate_trifecta(probs: Mapping[str, float]) -> dict[str, float]:
    p = _normalize(probs)
    expected = {
        f"{a}-{b}-{c}"
        for a, b, c in permutations(LANES, 3)
    }
    if set(p) != expected:
        raise ValueError("trifecta distribution must contain all 120 exact-order tickets")
    return p


def exacta_from_trifecta(probs: Mapping[str, float]) -> dict[str, float]:
    """P(a-b) = sum_c P(a-b-c)."""
    p = validate_trifecta(probs)
    out: dict[str, float] = defaultdict(float)
    for ticket, prob in p.items():
        a, b, _ = ticket.split("-")
        out[f"{a}-{b}"] += prob
    return _normalize(out)


def trio_from_trifecta(probs: Mapping[str, float]) -> dict[str, float]:
    """Unordered top-three probability = sum of all six permutations."""
    p = validate_trifecta(probs)
    out: dict[str, float] = defaultdict(float)
    for ticket, prob in p.items():
        key = "-".join(sorted(ticket.split("-"), key=int))
        out[key] += prob
    return _normalize(out)


def distribution_for_bet_type(probs: Mapping[str, float], bet_type: str) -> dict[str, float]:
    if bet_type == "trifecta":
        return validate_trifecta(probs)
    if bet_type == "exacta":
        return exacta_from_trifecta(probs)
    if bet_type == "trio":
        return trio_from_trifecta(probs)
    raise ValueError(f"unknown bet type: {bet_type}")


def ranked_tickets(probs: Mapping[str, float]) -> list[tuple[str, float]]:
    p = _normalize(probs)
    return sorted(p.items(), key=lambda kv: (-kv[1], kv[0]))


def select_fixed(probs: Mapping[str, float], n: int) -> tuple[str, ...]:
    if n < 1:
        raise ValueError("n must be >= 1")
    return tuple(ticket for ticket, _ in ranked_tickets(probs)[:n])


def select_coverage(
    probs: Mapping[str, float],
    target: float,
    *,
    max_tickets: int = COVERAGE_MAX_TICKETS,
) -> tuple[str, ...]:
    if not 0.0 < target <= 1.0:
        raise ValueError("target must be in (0,1]")
    if max_tickets < 1:
        raise ValueError("max_tickets must be >= 1")
    chosen: list[str] = []
    mass = 0.0
    for ticket, prob in ranked_tickets(probs):
        chosen.append(ticket)
        mass += prob
        if mass >= target or len(chosen) >= max_tickets:
            break
    return tuple(chosen)


def build_comparison_grid(trifecta_probs: Mapping[str, float]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for bet_type in BET_TYPES:
        probs = distribution_for_bet_type(trifecta_probs, bet_type)
        for n in FIXED_POINT_COUNTS:
            tickets = select_fixed(probs, n)
            rows.append({
                "bet_type": bet_type,
                "strategy": f"top{n}",
                "tickets": tickets,
                "ticket_count": len(tickets),
                "stake_yen": len(tickets) * STAKE_PER_TICKET_YEN,
                "probability_mass": sum(probs[t] for t in tickets),
            })
        for target in COVERAGE_TARGETS:
            tickets = select_coverage(probs, target)
            rows.append({
                "bet_type": bet_type,
                "strategy": f"coverage_{int(round(target * 100))}",
                "tickets": tickets,
                "ticket_count": len(tickets),
                "stake_yen": len(tickets) * STAKE_PER_TICKET_YEN,
                "probability_mass": sum(probs[t] for t in tickets),
            })
    return rows
