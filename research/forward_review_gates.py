# -*- coding: utf-8 -*-
"""Pure review-gate status for current prospective evidence tracks.

No I/O, no model logic, no promotion authority, no Production side effects.
The thresholds here only mirror already-frozen review contracts.
"""
from __future__ import annotations

from typing import Any

V4_FORMAL_REVIEW_DAYS = (10, 20, 30)
S03_M2_FULL_REVIEW_OBSERVATIONS = 100
DAY_STRENGTH_MIN_FUTURE_RESOLVED = 10
DAY_STRENGTH_MIN_KEEP = 3
DAY_STRENGTH_MIN_SKIP = 3


def _next_gate(current: int, gates: tuple[int, ...]) -> dict[str, Any]:
    for gate in gates:
        if current < gate:
            return {
                "status": "COLLECTING",
                "current": current,
                "next_gate": gate,
                "remaining": gate - current,
                "completed_gates": [x for x in gates if x <= current],
            }
    return {
        "status": "ALL_FROZEN_REVIEW_GATES_REACHED",
        "current": current,
        "next_gate": None,
        "remaining": 0,
        "completed_gates": list(gates),
    }


def v4_formal_gate(resolved_formal_days: int) -> dict[str, Any]:
    if resolved_formal_days < 0:
        raise ValueError("resolved_formal_days must be nonnegative")
    out = _next_gate(resolved_formal_days, V4_FORMAL_REVIEW_DAYS)
    return {
        "track": "V4_FORMAL_TOP2",
        **out,
        "rule_change_allowed": False,
        "promotion_allowed": False,
        "production_change": False,
    }


def s03_m2_gate(evaluated_observations: int) -> dict[str, Any]:
    if evaluated_observations < 0:
        raise ValueError("evaluated_observations must be nonnegative")
    remaining = max(0, S03_M2_FULL_REVIEW_OBSERVATIONS - evaluated_observations)
    return {
        "track": "S03_M2_POSITIVE_V1",
        "status": (
            "FULL_REVIEW_READY"
            if evaluated_observations >= S03_M2_FULL_REVIEW_OBSERVATIONS
            else "COLLECTING"
        ),
        "current": evaluated_observations,
        "next_gate": S03_M2_FULL_REVIEW_OBSERVATIONS,
        "remaining": remaining,
        "rule_change_allowed": False,
        "promotion_allowed": False,
        "production_change": False,
    }


def day_strength_gate(
    future_resolved_days: int,
    keep_days: int,
    skip_days: int,
) -> dict[str, Any]:
    for name, value in {
        "future_resolved_days": future_resolved_days,
        "keep_days": keep_days,
        "skip_days": skip_days,
    }.items():
        if value < 0:
            raise ValueError(f"{name} must be nonnegative")
    checks = {
        "future_resolved_days_ge_10": (
            future_resolved_days >= DAY_STRENGTH_MIN_FUTURE_RESOLVED
        ),
        "keep_days_ge_3": keep_days >= DAY_STRENGTH_MIN_KEEP,
        "skip_days_ge_3": skip_days >= DAY_STRENGTH_MIN_SKIP,
    }
    return {
        "track": "V4_FORMAL_DAY_STRENGTH_SHADOW_V1",
        "status": "DESCRIPTIVE_REVIEW_READY" if all(checks.values()) else "COLLECTING",
        "current": {
            "future_resolved_days": future_resolved_days,
            "keep_days": keep_days,
            "skip_days": skip_days,
        },
        "remaining": {
            "future_resolved_days": max(
                0, DAY_STRENGTH_MIN_FUTURE_RESOLVED - future_resolved_days
            ),
            "keep_days": max(0, DAY_STRENGTH_MIN_KEEP - keep_days),
            "skip_days": max(0, DAY_STRENGTH_MIN_SKIP - skip_days),
        },
        "checks": checks,
        "formal_action_changed": False,
        "promotion_allowed": False,
        "production_change": False,
    }


def current_baseline() -> dict[str, Any]:
    """Frozen baseline before natural 2026-09-27 result settlement."""
    return {
        "as_of": "2026-09-27T21:13:00+09:00",
        "v4_formal": v4_formal_gate(6),
        "s03_m2": s03_m2_gate(53),
        "day_strength": day_strength_gate(0, 0, 0),
        "notes": [
            "2026-09-27 formal artifact exists but is not counted resolved until official settlement",
            "day-strength evidence starts with target dates >= 2026-09-28",
            "review readiness never changes selector/TOP6/TOP2/stake automatically",
        ],
        "purchase_action": False,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(current_baseline(), ensure_ascii=False, indent=2, sort_keys=True))
