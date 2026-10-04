# -*- coding: utf-8 -*-
"""Pure preflight guard for the final matched-contract V4/V5 backtest.

This module intentionally performs no database access and no Railway action.
Its job is to prevent a comparative historical backtest from starting until:
1. the V5 candidate specification is explicitly frozen before outcome review;
2. a shared chronological time split is explicitly frozen;
3. the live historical readiness audit has passed separately.

Production remains V4. This module cannot promote a model, send LINE, buy,
change stake, mutate the database, or change Railway configuration.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Mapping, Sequence

from research import candidate_discovery_v4_contract as v4


CONTRACT = "MATCHED_CONTRACT_BACKTEST_PREFLIGHT_V1"
V5_SPEC_CONTRACT = "V5_RESEARCH_CANDIDATE_SPEC_V1"
TIME_SPLIT_CONTRACT = "MATCHED_CONTRACT_TIME_SPLIT_V1"
DATA_SERVICE = "postgres-hobby-fullhistory-candidate-v4"
HISTORICAL_START = date(2025, 7, 1)
HISTORICAL_RECONSTRUCTION_END = date(2026, 9, 30)


def v4_contract_snapshot() -> dict[str, Any]:
    """Return the frozen current V4 comparison baseline from executable code."""
    return {
        "generation": "V4",
        "course_coefficient": v4.COURSE_COEF,
        "opponent_pressure_coefficient": v4.OPPONENT_COEF,
        "opponent_pressure_role": "first_place_only",
        "motor2_beta": v4.MOTOR_BETA,
        "probability_temperature": v4.PROB_TEMP,
        "selector_signals": [
            "head_p1",
            "head_margin",
            "top3_mass",
            "concentration",
        ],
        "formal_races": v4.CORE_RACES,
        "formal_tickets_per_race": v4.CORE_TICKETS,
        "odds_read_for_selection": False,
        "expected_value_filter": False,
    }


def _baseline_fingerprint() -> tuple[Any, ...]:
    x = v4_contract_snapshot()
    return (
        x["course_coefficient"],
        x["opponent_pressure_coefficient"],
        x["opponent_pressure_role"],
        x["motor2_beta"],
        x["probability_temperature"],
        tuple(x["selector_signals"]),
        x["formal_races"],
        x["formal_tickets_per_race"],
        x["odds_read_for_selection"],
        x["expected_value_filter"],
    )


@dataclass(frozen=True)
class SplitWindow:
    name: str
    start_date: date
    end_date: date

    def as_json(self) -> dict[str, str]:
        if not self.name.strip():
            raise ValueError("split window name required")
        if self.end_date < self.start_date:
            raise ValueError("split window end_date must be >= start_date")
        return {
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
        }


def validate_time_split_manifest(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    if manifest is None:
        return {
            "valid": False,
            "reason": "TIME_SPLIT_NOT_FROZEN",
            "windows": [],
        }
    if str(manifest.get("contract") or "") != TIME_SPLIT_CONTRACT:
        return {
            "valid": False,
            "reason": "UNEXPECTED_TIME_SPLIT_CONTRACT",
            "windows": [],
        }
    if manifest.get("frozen_before_backtest_results") is not True:
        return {
            "valid": False,
            "reason": "TIME_SPLIT_NOT_PRE_FROZEN",
            "windows": [],
        }

    raw = manifest.get("windows")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        return {
            "valid": False,
            "reason": "TIME_SPLIT_WINDOWS_REQUIRED",
            "windows": [],
        }

    windows: list[SplitWindow] = []
    try:
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("split window must be object")
            windows.append(
                SplitWindow(
                    name=str(item.get("name") or ""),
                    start_date=date.fromisoformat(str(item.get("start_date") or "")),
                    end_date=date.fromisoformat(str(item.get("end_date") or "")),
                )
            )
        normalized = [x.as_json() for x in windows]
    except (TypeError, ValueError):
        return {
            "valid": False,
            "reason": "INVALID_TIME_SPLIT_WINDOW",
            "windows": [],
        }

    ordered = sorted(windows, key=lambda x: (x.start_date, x.end_date, x.name))
    if ordered != windows:
        return {
            "valid": False,
            "reason": "TIME_SPLIT_NOT_CHRONOLOGICAL",
            "windows": normalized,
        }
    if ordered[0].start_date < HISTORICAL_START:
        return {
            "valid": False,
            "reason": "TIME_SPLIT_BEFORE_SUPPORTED_HISTORY",
            "windows": normalized,
        }
    if ordered[-1].end_date > HISTORICAL_RECONSTRUCTION_END:
        return {
            "valid": False,
            "reason": "TIME_SPLIT_AFTER_RECONSTRUCTED_HISTORY",
            "windows": normalized,
        }
    for prev, cur in zip(ordered, ordered[1:]):
        if cur.start_date <= prev.end_date:
            return {
                "valid": False,
                "reason": "TIME_SPLIT_OVERLAP",
                "windows": normalized,
            }
    return {
        "valid": True,
        "reason": "PASS_PRE_FROZEN_SHARED_TIME_SPLIT",
        "windows": normalized,
    }


def validate_v5_candidate_manifest(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    if manifest is None:
        return {
            "valid": False,
            "comparative": False,
            "reason": "V5_CANDIDATE_SPEC_NOT_FROZEN",
        }
    if str(manifest.get("contract") or "") != V5_SPEC_CONTRACT:
        return {
            "valid": False,
            "comparative": False,
            "reason": "UNEXPECTED_V5_SPEC_CONTRACT",
        }
    if manifest.get("frozen_before_backtest_results") is not True:
        return {
            "valid": False,
            "comparative": False,
            "reason": "V5_SPEC_NOT_PRE_FROZEN",
        }
    if manifest.get("production_activation_allowed") is not False:
        return {
            "valid": False,
            "comparative": False,
            "reason": "V5_SPEC_MUST_BE_RESEARCH_ONLY",
        }
    if manifest.get("odds_read_for_selection") is not False:
        return {
            "valid": False,
            "comparative": False,
            "reason": "V5_SELECTOR_MUST_NOT_READ_ODDS",
        }
    if manifest.get("expected_value_filter") is not False:
        return {
            "valid": False,
            "comparative": False,
            "reason": "V5_SELECTOR_MUST_NOT_USE_EV_FILTER",
        }

    fp = manifest.get("comparison_fingerprint")
    if not isinstance(fp, Sequence) or isinstance(fp, (str, bytes)):
        return {
            "valid": False,
            "comparative": False,
            "reason": "V5_COMPARISON_FINGERPRINT_REQUIRED",
        }
    comparative = tuple(fp) != _baseline_fingerprint()
    return {
        "valid": True,
        "comparative": comparative,
        "reason": (
            "PASS_FROZEN_V5_COMPARATIVE_SPEC"
            if comparative
            else "V5_SPEC_IDENTICAL_TO_V4_BASELINE"
        ),
        "candidate_id": str(manifest.get("candidate_id") or ""),
    }


def build_preflight(
    *,
    v5_candidate_manifest: Mapping[str, Any] | None = None,
    time_split_manifest: Mapping[str, Any] | None = None,
    live_readiness_passed: bool = False,
) -> dict[str, Any]:
    v5_check = validate_v5_candidate_manifest(v5_candidate_manifest)
    split_check = validate_time_split_manifest(time_split_manifest)

    blockers: list[str] = []
    if not v5_check["valid"]:
        blockers.append(str(v5_check["reason"]))
    elif not v5_check["comparative"]:
        blockers.append("V5_NOT_COMPARATIVELY_DISTINCT_FROM_V4")
    if not split_check["valid"]:
        blockers.append(str(split_check["reason"]))
    if not live_readiness_passed:
        blockers.append("LIVE_READONLY_HISTORICAL_READINESS_PASS_REQUIRED")

    return {
        "contract": CONTRACT,
        "data_source": {
            "railway_service": DATA_SERVICE,
            "mode": "read_only_only",
            "historical_start": HISTORICAL_START.isoformat(),
            "historical_reconstruction_end": HISTORICAL_RECONSTRUCTION_END.isoformat(),
        },
        "v4_baseline": v4_contract_snapshot(),
        "v5_candidate": v5_check,
        "time_split": split_check,
        "historical_readiness": {
            "live_readonly_passed": bool(live_readiness_passed),
            "prospective_gate_credit": False,
        },
        "execution_ready": not blockers,
        "blockers": blockers,
        "evaluation_contract": {
            "same_input_rows": True,
            "same_time_split": True,
            "selection_materialized_before_outcome_evaluation": True,
            "outcomes_used_only_for_post_selection_scoring": True,
            "same_stake_for_comparison": True,
            "no_post_outcome_retuning": True,
        },
        "safety": {
            "database_write": False,
            "railway_config_change": False,
            "railway_service_creation": False,
            "production_change": False,
            "model_promotion": False,
            "line_send": False,
            "purchase_action": False,
        },
    }


def current_status() -> dict[str, Any]:
    """Current main intentionally blocks execution until missing freezes exist."""
    return build_preflight()


if __name__ == "__main__":
    import json

    out = current_status()
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    print(
        "MATCHED_CONTRACT_BACKTEST_PREFLIGHT_RESULT="
        + ("READY" if out["execution_ready"] else "BLOCKED")
    )
