# -*- coding: utf-8 -*-
"""Pure V5 research-candidate milestone contract.

This module does not define or activate a Production model. It only tracks
whether the already-preregistered evidence streams are mature enough to freeze
a V5 research candidate for further Forward evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Any

TARGET_FREEZE_DATE = date(2026, 10, 15)

V4_REQUIRED_RESOLVED_DAYS = 20
S03_REQUIRED_EVALUATED = 100
DAY_STRENGTH_REQUIRED_RESOLVED = 10
DAY_STRENGTH_REQUIRED_KEEP = 3
DAY_STRENGTH_REQUIRED_SKIP = 3


@dataclass(frozen=True)
class V5MilestoneInput:
    as_of: date
    v4_resolved_formal_days: int
    s03_m2_evaluated: int
    day_strength_future_resolved_days: int
    day_strength_keep_days: int
    day_strength_skip_days: int
    evidence_contract_clean: bool = True


def _nonnegative(name: str, value: int) -> None:
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")


def evaluate_v5_milestone(x: V5MilestoneInput) -> dict[str, Any]:
    for name in (
        "v4_resolved_formal_days",
        "s03_m2_evaluated",
        "day_strength_future_resolved_days",
        "day_strength_keep_days",
        "day_strength_skip_days",
    ):
        _nonnegative(name, int(getattr(x, name)))

    checks = {
        "v4_20_resolved_days": (
            x.v4_resolved_formal_days >= V4_REQUIRED_RESOLVED_DAYS
        ),
        "s03_100_evaluated": x.s03_m2_evaluated >= S03_REQUIRED_EVALUATED,
        "day_strength_10_resolved": (
            x.day_strength_future_resolved_days >= DAY_STRENGTH_REQUIRED_RESOLVED
        ),
        "day_strength_keep_ge_3": (
            x.day_strength_keep_days >= DAY_STRENGTH_REQUIRED_KEEP
        ),
        "day_strength_skip_ge_3": (
            x.day_strength_skip_days >= DAY_STRENGTH_REQUIRED_SKIP
        ),
        "evidence_contract_clean": bool(x.evidence_contract_clean),
    }
    evidence_ready = all(checks.values())

    return {
        "contract": "V5_RESEARCH_CANDIDATE_MILESTONE_V1",
        "target_freeze_date": TARGET_FREEZE_DATE.isoformat(),
        "input": {
            **asdict(x),
            "as_of": x.as_of.isoformat(),
        },
        "checks": checks,
        "remaining": {
            "v4_resolved_formal_days": max(
                0, V4_REQUIRED_RESOLVED_DAYS - x.v4_resolved_formal_days
            ),
            "s03_m2_evaluated": max(
                0, S03_REQUIRED_EVALUATED - x.s03_m2_evaluated
            ),
            "day_strength_future_resolved_days": max(
                0,
                DAY_STRENGTH_REQUIRED_RESOLVED
                - x.day_strength_future_resolved_days,
            ),
            "day_strength_keep_days": max(
                0, DAY_STRENGTH_REQUIRED_KEEP - x.day_strength_keep_days
            ),
            "day_strength_skip_days": max(
                0, DAY_STRENGTH_REQUIRED_SKIP - x.day_strength_skip_days
            ),
        },
        "status": (
            "V5_RESEARCH_CANDIDATE_FREEZE_REVIEW_READY"
            if evidence_ready
            else "COLLECTING_EVIDENCE"
        ),
        "evidence_ready": evidence_ready,
        "production_activation_allowed": False,
        "automatic_model_change_allowed": False,
        "automatic_selector_change_allowed": False,
        "automatic_stake_change_allowed": False,
        "purchase_action": False,
    }


def current_baseline() -> dict[str, Any]:
    # Before natural 2026-09-27 settlement.
    return evaluate_v5_milestone(
        V5MilestoneInput(
            as_of=date(2026, 9, 27),
            v4_resolved_formal_days=6,
            s03_m2_evaluated=53,
            day_strength_future_resolved_days=0,
            day_strength_keep_days=0,
            day_strength_skip_days=0,
            evidence_contract_clean=True,
        )
    )


if __name__ == "__main__":
    import json
    print(json.dumps(current_baseline(), ensure_ascii=False, indent=2, sort_keys=True))
