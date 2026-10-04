# -*- coding: utf-8 -*-
"""Pure preflight guard for the final matched-contract V4/V5 backtest.

No database access and no Railway action occur here.
Execution stays blocked until the candidate/time split are pre-frozen, the
prospective V5 admission gates are satisfied, and historical readiness passes.
"""
from __future__ import annotations

from dataclasses import dataclass
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
    return {
        "generation": "V4",
        "implementation": "research.candidate_discovery_v4_contract",
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
        return {"valid": False, "reason": "TIME_SPLIT_NOT_FROZEN", "windows": []}
    if str(manifest.get("contract") or "") != TIME_SPLIT_CONTRACT:
        return {"valid": False, "reason": "UNEXPECTED_TIME_SPLIT_CONTRACT", "windows": []}
    if manifest.get("frozen_before_backtest_results") is not True:
        return {"valid": False, "reason": "TIME_SPLIT_NOT_PRE_FROZEN", "windows": []}

    raw = manifest.get("windows")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        return {"valid": False, "reason": "TIME_SPLIT_WINDOWS_REQUIRED", "windows": []}

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
        return {"valid": False, "reason": "INVALID_TIME_SPLIT_WINDOW", "windows": []}

    ordered = sorted(windows, key=lambda x: (x.start_date, x.end_date, x.name))
    if ordered != windows:
        return {"valid": False, "reason": "TIME_SPLIT_NOT_CHRONOLOGICAL", "windows": normalized}
    if ordered[0].start_date < HISTORICAL_START:
        return {"valid": False, "reason": "TIME_SPLIT_BEFORE_SUPPORTED_HISTORY", "windows": normalized}
    if ordered[-1].end_date > HISTORICAL_RECONSTRUCTION_END:
        return {"valid": False, "reason": "TIME_SPLIT_AFTER_RECONSTRUCTED_HISTORY", "windows": normalized}
    for prev, cur in zip(ordered, ordered[1:]):
        if cur.start_date <= prev.end_date:
            return {"valid": False, "reason": "TIME_SPLIT_OVERLAP", "windows": normalized}
    return {
        "valid": True,
        "reason": "PASS_PRE_FROZEN_SHARED_TIME_SPLIT",
        "windows": normalized,
    }


def validate_v5_candidate_manifest(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    if manifest is None:
        return {"valid": False, "comparative": False, "reason": "V5_CANDIDATE_SPEC_NOT_FROZEN"}
    if str(manifest.get("contract") or "") != V5_SPEC_CONTRACT:
        return {"valid": False, "comparative": False, "reason": "UNEXPECTED_V5_SPEC_CONTRACT"}
    if manifest.get("frozen_before_backtest_results") is not True:
        return {"valid": False, "comparative": False, "reason": "V5_SPEC_NOT_PRE_FROZEN"}
    if manifest.get("production_activation_allowed") is not False:
        return {"valid": False, "comparative": False, "reason": "V5_SPEC_MUST_BE_RESEARCH_ONLY"}
    if manifest.get("odds_read_for_selection") is not False:
        return {"valid": False, "comparative": False, "reason": "V5_SELECTOR_MUST_NOT_READ_ODDS"}
    if manifest.get("expected_value_filter") is not False:
        return {"valid": False, "comparative": False, "reason": "V5_SELECTOR_MUST_NOT_USE_EV_FILTER"}

    candidate_id = str(manifest.get("candidate_id") or "").strip()
    if not candidate_id:
        return {"valid": False, "comparative": False, "reason": "V5_CANDIDATE_ID_REQUIRED"}

    delta = manifest.get("comparison_delta")
    if not isinstance(delta, Sequence) or isinstance(delta, (str, bytes)):
        return {"valid": False, "comparative": False, "reason": "V5_COMPARISON_DELTA_REQUIRED"}
    normalized_delta = [str(x).strip() for x in delta if str(x).strip()]
    comparative = bool(normalized_delta)
    return {
        "valid": True,
        "comparative": comparative,
        "reason": (
            "PASS_FROZEN_V5_COMPARATIVE_SPEC"
            if comparative
            else "V5_SPEC_IDENTICAL_TO_V4_BASELINE"
        ),
        "candidate_id": candidate_id,
        "comparison_delta": normalized_delta,
    }


def validate_prospective_gate_state(
    candidate_manifest: Mapping[str, Any] | None,
    gate_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not candidate_manifest or not isinstance(candidate_manifest.get("prospective_admission_gate"), Mapping):
        return {"valid": False, "reason": "V5_PROSPECTIVE_GATE_CONTRACT_REQUIRED"}
    if gate_state is None:
        return {"valid": False, "reason": "V5_PROSPECTIVE_GATE_STATE_REQUIRED"}

    req = candidate_manifest["prospective_admission_gate"]
    try:
        v4_days = int(gate_state.get("formal_v4_resolved_days"))
        s03_n = int(gate_state.get("s03_m2_officially_evaluated"))
    except (TypeError, ValueError):
        return {"valid": False, "reason": "V5_PROSPECTIVE_GATE_STATE_INVALID"}

    evidence_clean = gate_state.get("evidence_contract_clean") is True
    v4_min = int(req.get("formal_v4_resolved_days_min") or 0)
    s03_min = int(req.get("s03_m2_officially_evaluated_min") or 0)
    clean_required = req.get("evidence_contract_clean_required") is True

    blockers: list[str] = []
    if v4_days < v4_min:
        blockers.append("FORMAL_V4_20_NOT_REACHED")
    if s03_n < s03_min:
        blockers.append("S03_M2_100_NOT_REACHED")
    if clean_required and not evidence_clean:
        blockers.append("EVIDENCE_CONTRACT_NOT_CLEAN")

    return {
        "valid": not blockers,
        "reason": "PASS_PROSPECTIVE_V5_ADMISSION_GATES" if not blockers else "PROSPECTIVE_V5_ADMISSION_BLOCKED",
        "blockers": blockers,
        "observed": {
            "formal_v4_resolved_days": v4_days,
            "s03_m2_officially_evaluated": s03_n,
            "evidence_contract_clean": evidence_clean,
        },
        "required": {
            "formal_v4_resolved_days_min": v4_min,
            "s03_m2_officially_evaluated_min": s03_min,
            "evidence_contract_clean_required": clean_required,
        },
    }


def build_preflight(
    *,
    v5_candidate_manifest: Mapping[str, Any] | None = None,
    time_split_manifest: Mapping[str, Any] | None = None,
    prospective_gate_state: Mapping[str, Any] | None = None,
    live_readiness_passed: bool = False,
) -> dict[str, Any]:
    v5_check = validate_v5_candidate_manifest(v5_candidate_manifest)
    split_check = validate_time_split_manifest(time_split_manifest)
    gate_check = validate_prospective_gate_state(v5_candidate_manifest, prospective_gate_state)

    blockers: list[str] = []
    if not v5_check["valid"]:
        blockers.append(str(v5_check["reason"]))
    elif not v5_check["comparative"]:
        blockers.append("V5_NOT_COMPARATIVELY_DISTINCT_FROM_V4")
    if not split_check["valid"]:
        blockers.append(str(split_check["reason"]))
    if not gate_check["valid"]:
        if gate_check.get("blockers"):
            blockers.extend(str(x) for x in gate_check["blockers"])
        else:
            blockers.append(str(gate_check["reason"]))
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
        "prospective_admission": gate_check,
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
    """Use the frozen research manifests; live gate/readiness still fail closed."""
    from research.v5_matched_backtest_contract import (
        shared_time_split_manifest,
        v5_candidate_manifest,
    )

    return build_preflight(
        v5_candidate_manifest=v5_candidate_manifest(),
        time_split_manifest=shared_time_split_manifest(),
        prospective_gate_state=None,
        live_readiness_passed=False,
    )


if __name__ == "__main__":
    import json

    out = current_status()
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    print(
        "MATCHED_CONTRACT_BACKTEST_PREFLIGHT_RESULT="
        + ("READY" if out["execution_ready"] else "BLOCKED")
    )
