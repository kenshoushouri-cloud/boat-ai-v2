# -*- coding: utf-8 -*-
"""Pure V5 freeze-review packet builder.

Consumes already-frozen combined Forward checkpoint output and optionally a
future day-strength summary. Produces a review packet only. It never decides
Production activation or changes any model/selector/stake.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from research.v5_candidate_milestone import evaluate_v5_core_progress


COMBINED_CONTRACT = "forward_combined_manual_checkpoint_v1"
PACKET_CONTRACT = "V5_FREEZE_REVIEW_PACKET_V1"


def _roi_gt_100(block: Mapping[str, Any]) -> bool | None:
    value = block.get("roi_pct")
    if value is None:
        return None
    return float(value) > 100.0


def _optional_day_strength(summary: Mapping[str, Any] | None) -> dict[str, Any]:
    if summary is None:
        return {
            "supplied": False,
            "admission_ready": False,
            "required_for_core_freeze": False,
        }

    resolved = int(summary.get("future_resolved_days") or 0)
    keep = int(summary.get("keep_days") or 0)
    skip = int(summary.get("skip_days") or 0)
    return {
        "supplied": True,
        "future_resolved_days": resolved,
        "keep_days": keep,
        "skip_days": skip,
        "admission_ready": resolved >= 10 and keep >= 3 and skip >= 3,
        "required_for_core_freeze": False,
    }


def build_v5_review_packet(
    combined: Mapping[str, Any],
    *,
    day_strength_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if str(combined.get("contract") or "") != COMBINED_CONTRACT:
        raise ValueError("unexpected combined checkpoint contract")

    v4 = combined.get("v4_formal") or {}
    s03 = combined.get("s03_m2") or {}
    v5 = combined.get("v5_core_milestone") or {}
    safety = combined.get("safety") or {}

    if safety.get("production_change") is not False:
        raise ValueError("combined checkpoint must be production-neutral")
    if safety.get("buy") is not False or safety.get("purchase_action") is not False:
        raise ValueError("combined checkpoint must keep purchase disabled")

    v4_top2 = v4.get("top2") or {}
    s03_overall = s03.get("overall") or {}
    v4_days = int(v4.get("resolved_formal_days") or 0)
    s03_evaluated = int(s03_overall.get("evaluated") or 0)

    milestone_source = "embedded_combined_checkpoint"
    if "core_evidence_ready" not in v5:
        end_date = date.fromisoformat(str(combined.get("end_date") or ""))
        v5 = evaluate_v5_core_progress(
            as_of=end_date,
            v4_resolved_formal_days=v4_days,
            s03_m2_evaluated=s03_evaluated,
            evidence_contract_clean=True,
        )
        milestone_source = "derived_from_frozen_v4_s03_counts"

    core_ready = bool(v5.get("core_evidence_ready"))

    return {
        "contract": PACKET_CONTRACT,
        "end_date": combined.get("end_date"),
        "target_freeze_date": v5.get("target_freeze_date", "2026-10-15"),
        "core_review_status": (
            "CORE_EVIDENCE_READY_FOR_HUMAN_FREEZE_REVIEW"
            if core_ready
            else "COLLECTING_CORE_EVIDENCE"
        ),
        "core_evidence_ready": core_ready,
        "v4_formal": {
            "resolved_formal_days": v4_days,
            "top2": v4_top2,
            "robustness": v4.get("robustness") or {},
            "review_gate": v4.get("review_gate") or {},
            "roi_gt_100_descriptive": _roi_gt_100(v4_top2),
        },
        "s03_m2": {
            "coverage": s03.get("coverage") or {},
            "overall": s03_overall,
            "risk": s03.get("risk") or {},
            "chronological_halves": s03.get("chronological_halves") or {},
            "day_bootstrap": s03.get("day_bootstrap") or {},
            "review_gate": s03.get("review_gate") or {},
            "roi_gt_100_descriptive": _roi_gt_100(s03_overall),
        },
        "v5_core_milestone": v5,
        "v5_core_milestone_source": milestone_source,
        "optional_layers": {
            "day_strength": _optional_day_strength(day_strength_summary),
            "f_count": {
                "supplied": False,
                "admission_ready": False,
                "required_for_core_freeze": False,
                "explicit_live_approval_required": True,
            },
        },
        "decision_boundary": {
            "human_review_required": True,
            "automatic_candidate_freeze_allowed": False,
            "automatic_production_activation_allowed": False,
            "automatic_model_change_allowed": False,
            "automatic_selector_change_allowed": False,
            "automatic_stake_change_allowed": False,
            "line_send_allowed": False,
            "purchase_action": False,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--combined-json", required=True)
    ap.add_argument("--day-strength-json")
    ap.add_argument("--output", default="v5-freeze-review-packet.json")
    args = ap.parse_args()

    combined = json.loads(Path(args.combined_json).read_text(encoding="utf-8"))
    day_strength = None
    if args.day_strength_json:
        day_strength = json.loads(
            Path(args.day_strength_json).read_text(encoding="utf-8")
        )

    packet = build_v5_review_packet(
        combined,
        day_strength_summary=day_strength,
    )
    Path(args.output).write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("V5_FREEZE_REVIEW_PACKET=" + json.dumps(packet, sort_keys=True))
    print("V5_FREEZE_REVIEW_PACKET_RESULT=PASS_PURE_REVIEW_ONLY")


if __name__ == "__main__":
    main()
