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

    core_checks = {
        "v4_20_resolved_days": (
            x.v4_resolved_formal_days >= V4_REQUIRED_RESOLVED_DAYS
        ),
        "s03_100_evaluated": x.s03_m2_evaluated >= S03_REQUIRED_EVALUATED,
        "evidence_contract_clean": bool(x.evidence_contract_clean),
    }
    day_strength_checks = {
        "day_strength_10_resolved": (
            x.day_strength_future_resolved_days >= DAY_STRENGTH_REQUIRED_RESOLVED
        ),
        "day_strength_keep_ge_3": (
            x.day_strength_keep_days >= DAY_STRENGTH_REQUIRED_KEEP
        ),
        "day_strength_skip_ge_3": (
            x.day_strength_skip_days >= DAY_STRENGTH_REQUIRED_SKIP
        ),
    }
    core_ready = all(core_checks.values())
    day_strength_admission_ready = all(day_strength_checks.values())

    return {
        "contract": "V5_RESEARCH_CANDIDATE_MILESTONE_V1",
        "target_freeze_date": TARGET_FREEZE_DATE.isoformat(),
        "input": {
            **asdict(x),
            "as_of": x.as_of.isoformat(),
        },
        "core_checks": core_checks,
        "optional_layer_checks": {
            "day_strength": day_strength_checks,
        },
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
            "V5_CORE_FREEZE_REVIEW_READY"
            if core_ready
            else "COLLECTING_CORE_EVIDENCE"
        ),
        "core_evidence_ready": core_ready,
        "optional_layers": {
            "day_strength": {
                "admission_ready": day_strength_admission_ready,
                "required_for_core_freeze": False,
                "remain_shadow_if_not_ready": True,
            },
            "f_count": {
                "admission_ready": False,
                "required_for_core_freeze": False,
                "explicit_live_approval_required": True,
            },
        },
        "production_activation_allowed": False,
        "automatic_model_change_allowed": False,
        "automatic_selector_change_allowed": False,
        "automatic_stake_change_allowed": False,
        "purchase_action": False,
    }


def evaluate_v5_core_progress(
    *,
    as_of: date,
    v4_resolved_formal_days: int,
    s03_m2_evaluated: int,
    evidence_contract_clean: bool = True,
) -> dict[str, Any]:
    """Core-only progress for routine combined checkpoints.

    Optional-layer counts are intentionally not inferred here.
    """
    result = evaluate_v5_milestone(
        V5MilestoneInput(
            as_of=as_of,
            v4_resolved_formal_days=v4_resolved_formal_days,
            s03_m2_evaluated=s03_m2_evaluated,
            day_strength_future_resolved_days=0,
            day_strength_keep_days=0,
            day_strength_skip_days=0,
            evidence_contract_clean=evidence_contract_clean,
        )
    )
    return {
        "contract": result["contract"],
        "target_freeze_date": result["target_freeze_date"],
        "status": result["status"],
        "core_evidence_ready": result["core_evidence_ready"],
        "core_checks": result["core_checks"],
        "remaining": {
            "v4_resolved_formal_days": result["remaining"][
                "v4_resolved_formal_days"
            ],
            "s03_m2_evaluated": result["remaining"]["s03_m2_evaluated"],
        },
        "optional_layers_not_evaluated_here": [
            "day_strength",
            "f_count",
        ],
        "production_activation_allowed": False,
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
